import { EVENT_SEMANTICS } from "./event-semantics.generated.mjs?v=20260823-semantic-v1";
import {
  classifyPublicCategory,
  foldPublicCategoryText,
} from "./public-category-rules.mjs?v=20260823-taxonomy-v2";

const FORMAT_RULES = compileDimensionRules(EVENT_SEMANTICS.format.rules);
const AUDIENCE_RULES = compileDimensionRules(EVENT_SEMANTICS.audience.rules);
const SEMANTIC_EVIDENCE_KINDS = new Set(
  EVENT_SEMANTICS.secondary_domain.semantic_evidence_kinds || [],
);

function compileDimensionRules(rules = []) {
  return [...rules]
    .sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0))
    .map((rule) => ({
      ...rule,
      regexes: (rule.patterns || []).map((pattern) => new RegExp(pattern, "u")),
    }));
}

function textForScope(event, scope) {
  if (scope === "title") return foldPublicCategoryText(event?.title);
  return foldPublicCategoryText([
    event?.description,
    ...(event?.tags || []),
  ].filter(Boolean).join(" "));
}

function matchDimension(event, spec, compiledRules) {
  for (const scope of ["title", "description"]) {
    const text = textForScope(event, scope);
    if (!text) continue;
    for (const rule of compiledRules) {
      const matchedPattern = rule.regexes.find((regex) => regex.test(text));
      if (!matchedPattern) continue;
      const value = rule.value || spec.fallback;
      return {
        value,
        label: spec.values?.[value]?.label || value,
        confidence: scope === "title" ? "high" : "medium",
        evidence: [{
          rule: rule.id,
          scope,
          pattern: matchedPattern.source,
          priority: Number(rule.priority || 0),
        }],
      };
    }
  }
  const value = spec.fallback;
  return {
    value,
    label: spec.values?.[value]?.label || value,
    confidence: "unspecified",
    evidence: [],
  };
}

function lifecycleValue(event) {
  const lifecycle = event?.lifecycle;
  if (typeof lifecycle === "string" && lifecycle.trim()) {
    return { value: lifecycle.trim(), source: "lifecycle" };
  }
  if (lifecycle && typeof lifecycle === "object") {
    for (const key of ["state", "kind", "type", "value"]) {
      const value = String(lifecycle?.[key] || "").trim();
      if (value) return { value, source: `lifecycle.${key}` };
    }
  }
  const contentKind = String(event?.content_kind || "").trim();
  if (contentKind) return { value: contentKind, source: "content_kind" };
  return {
    value: EVENT_SEMANTICS.lifecycle.fallback,
    source: null,
  };
}

function secondaryDomains(classification) {
  const primaryId = classification?.category?.id || null;
  if (!primaryId || primaryId === "unclassified") return [];

  const minimumScore = Number(EVENT_SEMANTICS.secondary_domain.minimum_score || 0);
  const ratio = Number(EVENT_SEMANTICS.secondary_domain.minimum_ratio_to_primary || 0);
  const threshold = Math.max(minimumScore, Number(classification.score || 0) * ratio);
  const requireSemanticEvidence = Boolean(
    EVENT_SEMANTICS.secondary_domain.require_semantic_evidence,
  );

  return (classification.candidates || [])
    .filter((candidate) => candidate?.category?.id && candidate.category.id !== primaryId)
    .filter((candidate) => Number(candidate.score || 0) >= threshold)
    .filter((candidate) => (
      !requireSemanticEvidence
      || (candidate.evidence || []).some((item) => SEMANTIC_EVIDENCE_KINDS.has(item.kind))
    ))
    .map((candidate) => candidate.category.id);
}

export function classifyEventFormat(event) {
  return matchDimension(event, EVENT_SEMANTICS.format, FORMAT_RULES);
}

export function classifyEventAudience(event) {
  return matchDimension(event, EVENT_SEMANTICS.audience, AUDIENCE_RULES);
}

export function buildEventSemantics(event = {}) {
  const classification = classifyPublicCategory(event);
  const format = classifyEventFormat(event);
  const audience = classifyEventAudience(event);
  const lifecycle = lifecycleValue(event);
  const primaryDomain = classification.category.id === "unclassified"
    ? null
    : classification.category.id;

  return {
    schema_version: EVENT_SEMANTICS.schema_version,
    category: classification.category,
    classification_state: primaryDomain ? "classified" : "unclassified",
    primary_domain: primaryDomain,
    secondary_domains: secondaryDomains(classification),
    confidence: classification.confidence,
    score: classification.score,
    evidence: classification.evidence,
    domain_candidates: classification.candidates || [],
    source_category: classification.source_category,
    format: format.value,
    audience: audience.value,
    lifecycle: lifecycle.value,
    trace: {
      format,
      audience,
      lifecycle,
    },
  };
}

export function annotateEventSemantics(event = {}) {
  return {
    ...event,
    semantics: buildEventSemantics(event),
  };
}
