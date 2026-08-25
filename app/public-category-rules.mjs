import {
  PUBLIC_CATEGORIES,
  PUBLIC_CATEGORY_ALIASES,
  PUBLIC_CATEGORY_GROUPS,
  PUBLIC_CATEGORY_LABEL_ALIASES,
  PUBLIC_CATEGORY_TAXONOMY,
  PUBLIC_EVENT_TYPE_LABELS,
} from "./public-category-taxonomy.generated.mjs";

const RULES = PUBLIC_CATEGORY_TAXONOMY.rules;
const FALLBACK_ID = PUBLIC_CATEGORY_TAXONOMY.fallback_category;
const CATEGORY_ORDER = new Map(
  (PUBLIC_CATEGORY_TAXONOMY.category_order || Object.keys(PUBLIC_CATEGORIES))
    .map((id, index) => [id, index]),
);
const TITLE_EVIDENCE_RULES = RULES.title_evidence.map((rule) => ({
  ...rule,
  regex: new RegExp(rule.pattern, "u"),
}));
const DESCRIPTION_EVIDENCE_RULES = RULES.description_evidence.map((rule) => ({
  ...rule,
  regex: new RegExp(rule.pattern, "u"),
}));
const SOURCE_TITLE_EVIDENCE_RULES = (RULES.source_title_evidence || []).map((rule) => ({
  ...rule,
  regex: new RegExp(rule.pattern, "u"),
}));
const SUMMER_PROGRAM_RE = new RegExp(RULES.summer_program_title_pattern, "u");
const SUMMER_REGISTRATION_RE = new RegExp(RULES.summer_registration_title_pattern, "u");
const SUMMER_PROGRAM_EVENT_TYPES = new Set(RULES.summer_program_event_types);
const SEMANTIC_NOISE_FIELDS = RULES.semantic_noise_fields || [];
const SEMANTIC_NOISE_PHRASES = RULES.semantic_noise_phrases || [];
const TAG_CATEGORY_WEIGHT = Number(RULES.tag_category_weight || 0);
const TAG_CATEGORY_ALIASES = RULES.tag_category_aliases || {};

export function foldPublicCategoryText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sourceCategory(event) {
  const source = event?.semantics?.source_category
    || event?.primary_category
    || event?.categories?.[0]
    || null;
  const label = String(source?.label || "").trim();
  const id = String(source?.id || foldPublicCategoryText(label).replace(/\s+/g, "-"))
    .trim()
    .toLocaleLowerCase("es");
  return { id, label };
}

export function canonicalPublicCategory(category) {
  const raw = typeof category === "string" ? { id: category, label: "" } : (category || {});
  const label = String(raw?.label || "").trim();
  const id = String(raw?.id || foldPublicCategoryText(label).replace(/\s+/g, "-"))
    .trim()
    .toLocaleLowerCase("es");
  const labelKey = foldPublicCategoryText(label);
  const canonicalId = PUBLIC_CATEGORY_ALIASES[id]
    || PUBLIC_CATEGORY_LABEL_ALIASES[labelKey]
    || (PUBLIC_CATEGORIES[id] ? id : null);
  if (!canonicalId) return id || label ? { id, label: label || id } : null;
  return { id: canonicalId, label: PUBLIC_CATEGORIES[canonicalId].label };
}

export function canonicalPublicCategoryId(category) {
  return canonicalPublicCategory(category)?.id || null;
}

export function isPublicCategoryInGroup(category, groupName) {
  const id = canonicalPublicCategoryId(category);
  return Boolean(id && (PUBLIC_CATEGORY_GROUPS[groupName] || []).includes(id));
}

export function publicCategorySymbol(category) {
  const id = canonicalPublicCategoryId(category);
  return id && PUBLIC_CATEGORIES[id]?.symbol
    ? PUBLIC_CATEGORIES[id].symbol
    : PUBLIC_CATEGORIES[FALLBACK_ID].symbol;
}

export function publicEventTypeLabel(eventType) {
  return PUBLIC_EVENT_TYPE_LABELS[String(eventType || "")] || null;
}

function category(id) {
  const resolvedId = PUBLIC_CATEGORIES[id] ? id : FALLBACK_ID;
  return { id: resolvedId, label: PUBLIC_CATEGORIES[resolvedId].label };
}

function isThematicCategory(id) {
  return Boolean(id && PUBLIC_CATEGORIES[id]?.thematic === true);
}

function isSummerProgram(event) {
  if (!SUMMER_PROGRAM_EVENT_TYPES.has(String(event?.event_type || ""))) return false;
  const title = foldPublicCategoryText(event?.title);
  return SUMMER_PROGRAM_RE.test(title) || SUMMER_REGISTRATION_RE.test(title);
}

function scalarNoiseValues(value) {
  if (typeof value === "string") return [value];
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  const values = ["name", "label", "title", "address", "city", "venue"]
    .map((key) => value[key])
    .filter(Boolean)
    .map(String);
  const venue = foldPublicCategoryText(value.venue);
  const city = foldPublicCategoryText(value.city);
  if (venue && city && venue.endsWith(` ${city}`)) {
    const shortVenue = venue.slice(0, -(city.length + 1)).trim();
    if (shortVenue.length >= 4) values.push(shortVenue);
  }
  return values;
}

function semanticNoiseValues(event) {
  const values = [];
  for (const field of SEMANTIC_NOISE_FIELDS) {
    values.push(...scalarNoiseValues(event?.[field]));
  }
  values.push(...scalarNoiseValues(event?.source?.name));
  return [...new Set(values
    .map(foldPublicCategoryText)
    .filter((value) => value.length >= 4))]
    .sort((a, b) => b.length - a.length);
}

function escapedRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function stripSemanticNoise(text, event) {
  let cleaned = foldPublicCategoryText(text);
  for (const phrase of SEMANTIC_NOISE_PHRASES) {
    const token = foldPublicCategoryText(phrase);
    if (token) cleaned = cleaned.replace(new RegExp(`\\b${escapedRegex(token)}\\b`, "gu"), " ");
  }
  for (const token of semanticNoiseValues(event)) {
    cleaned = cleaned.replace(new RegExp(`\\b${escapedRegex(token)}\\b`, "gu"), " ");
  }
  return cleaned.replace(/\s+/g, " ").trim();
}

function descriptionEvidenceText(event) {
  return stripSemanticNoise([
    event?.semantics?.category_evidence_text,
    event?.description,
    ...(event?.tags || []),
  ].filter(Boolean).join(" "), event);
}

function addEvidence(scores, evidence, categoryId, weight, kind, value) {
  if (!isThematicCategory(categoryId) || !weight) return;
  scores.set(categoryId, (scores.get(categoryId) || 0) + weight);
  evidence.push({ category: categoryId, weight, kind, value });
}

function addRuleEvidence(scores, evidence, text, rules, kind) {
  if (!text) return;
  for (const rule of rules) {
    if (rule.regex.test(text)) {
      addEvidence(scores, evidence, rule.category, Number(rule.weight || 0), kind, rule.pattern);
    }
  }
}

function addSourceTitleEvidence(scores, evidence, event) {
  const title = foldPublicCategoryText(event?.title);
  const sourceId = String(event?.source_id || "").trim();
  if (!title || !sourceId) return;
  for (const rule of SOURCE_TITLE_EVIDENCE_RULES) {
    if (String(rule.source_id || "") !== sourceId) continue;
    if (!rule.regex.test(title)) continue;
    addEvidence(
      scores,
      evidence,
      rule.category,
      Number(rule.weight || 0),
      "source_title",
      rule.reason || rule.pattern,
    );
  }
}

function addTagCategoryEvidence(scores, evidence, event) {
  if (!TAG_CATEGORY_WEIGHT) return;
  const seen = new Set();
  for (const rawTag of event?.tags || []) {
    const tag = foldPublicCategoryText(rawTag);
    const categoryId = TAG_CATEGORY_ALIASES[tag];
    const key = `${categoryId || ""}|${tag}`;
    if (!categoryId || seen.has(key)) continue;
    seen.add(key);
    addEvidence(scores, evidence, categoryId, TAG_CATEGORY_WEIGHT, "source_tag", rawTag);
  }
}

function confidenceForScore(score) {
  if (score >= 120) return "high";
  if (score >= 70) return "medium";
  return score >= Number(RULES.minimum_score || 1) ? "low" : "unclassified";
}

function rankedCandidates(scores, evidence) {
  return [...scores.entries()]
    .filter(([, score]) => score > 0)
    .sort((a, b) => (
      b[1] - a[1]
      || (CATEGORY_ORDER.get(a[0]) ?? Number.MAX_SAFE_INTEGER)
        - (CATEGORY_ORDER.get(b[0]) ?? Number.MAX_SAFE_INTEGER)
    ))
    .map(([categoryId, score]) => ({
      category: category(categoryId),
      score,
      confidence: confidenceForScore(score),
      evidence: evidence.filter((item) => item.category === categoryId),
    }));
}

export function classifyPublicCategory(event) {
  const scores = new Map();
  const evidence = [];
  const source = sourceCategory(event);
  const canonicalSource = canonicalPublicCategory(source);
  const recoveryHint = canonicalPublicCategory(event?.editorial?.category_recovery_hint || null);

  if (isSummerProgram(event)) {
    addEvidence(scores, evidence, "cursos-talleres-campus", 180, "event_type", "summer_program");
  }

  if (canonicalSource && isThematicCategory(canonicalSource.id)) {
    addEvidence(
      scores,
      evidence,
      canonicalSource.id,
      Number(RULES.source_category_weight || 0),
      "source_category",
      source.id || source.label,
    );
  }

  if (recoveryHint && isThematicCategory(recoveryHint.id)) {
    addEvidence(
      scores,
      evidence,
      recoveryHint.id,
      Number(RULES.recovery_hint_weight || RULES.source_category_weight || 0),
      "recovery_hint",
      String(event?.editorial?.category_recovery_hint || ""),
    );
  }

  // Generic venue/organizer/source-name text is intentionally excluded.
  // Verified sparse-title exceptions remain declarative in source_title_evidence.
  addTagCategoryEvidence(scores, evidence, event);
  addSourceTitleEvidence(scores, evidence, event);
  addRuleEvidence(
    scores,
    evidence,
    stripSemanticNoise(event?.title, event),
    TITLE_EVIDENCE_RULES,
    "title",
  );
  addRuleEvidence(
    scores,
    evidence,
    descriptionEvidenceText(event),
    DESCRIPTION_EVIDENCE_RULES,
    "description",
  );

  const candidates = rankedCandidates(scores, evidence);
  const minimumScore = Number(RULES.minimum_score || 1);
  const winner = candidates.find((candidate) => candidate.score >= minimumScore) || null;

  if (!winner) {
    return {
      category: category(FALLBACK_ID),
      confidence: "unclassified",
      score: candidates[0]?.score || 0,
      evidence,
      source_category: source,
      candidates,
    };
  }

  return {
    category: winner.category,
    confidence: winner.confidence,
    score: winner.score,
    evidence,
    source_category: source,
    candidates,
  };
}

export function resolvePublicCategory(event) {
  return classifyPublicCategory(event).category;
}
