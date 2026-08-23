import {
  PUBLIC_CATEGORIES,
  PUBLIC_CATEGORY_ALIASES,
  PUBLIC_CATEGORY_GROUPS,
  PUBLIC_CATEGORY_LABEL_ALIASES,
  PUBLIC_CATEGORY_TAXONOMY,
  PUBLIC_EVENT_TYPE_LABELS,
} from "./public-category-taxonomy.generated.mjs";

const RULES = PUBLIC_CATEGORY_TAXONOMY.rules;
const EXPLICIT_TITLE_RULES = RULES.explicit_title.map((rule) => ({
  ...rule,
  regex: new RegExp(rule.pattern, "u"),
}));
const CULTURE_EVIDENCE_RULES = RULES.culture_evidence.map((rule) => ({
  ...rule,
  regex: new RegExp(rule.pattern, "u"),
}));
const SUMMER_PROGRAM_RE = new RegExp(RULES.summer_program_title_pattern, "u");
const SUMMER_REGISTRATION_RE = new RegExp(RULES.summer_registration_title_pattern, "u");
const SUMMER_PROGRAM_EVENT_TYPES = new Set(RULES.summer_program_event_types);

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
  const source = event?.primary_category || event?.categories?.[0] || null;
  const label = String(source?.label || "").trim();
  const id = String(source?.id || foldPublicCategoryText(label).replace(/\s+/g, "-")).trim().toLocaleLowerCase("es");
  return { id, label };
}

export function canonicalPublicCategory(category) {
  const raw = typeof category === "string" ? { id: category, label: "" } : (category || {});
  const label = String(raw?.label || "").trim();
  const id = String(raw?.id || foldPublicCategoryText(label).replace(/\s+/g, "-")).trim().toLocaleLowerCase("es");
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
  return id && PUBLIC_CATEGORIES[id]?.symbol ? PUBLIC_CATEGORIES[id].symbol : PUBLIC_CATEGORIES[PUBLIC_CATEGORY_TAXONOMY.fallback_category].symbol;
}

export function publicEventTypeLabel(eventType) {
  return PUBLIC_EVENT_TYPE_LABELS[String(eventType || "")] || null;
}

function category(id) {
  const config = PUBLIC_CATEGORIES[id] || PUBLIC_CATEGORIES[PUBLIC_CATEGORY_TAXONOMY.fallback_category];
  return { id: PUBLIC_CATEGORIES[id] ? id : PUBLIC_CATEGORY_TAXONOMY.fallback_category, label: config.label };
}

function evidenceText(event) {
  return foldPublicCategoryText([
    event?.title,
    event?.description,
    event?.organizer,
    event?.source_name,
    ...(event?.tags || []),
  ].filter(Boolean).join(" "));
}

function isSummerProgram(event) {
  if (!SUMMER_PROGRAM_EVENT_TYPES.has(String(event?.event_type || ""))) return false;
  const title = foldPublicCategoryText(event?.title);
  return SUMMER_PROGRAM_RE.test(title) || SUMMER_REGISTRATION_RE.test(title);
}

function categoryFromRules(text, rules) {
  for (const rule of rules) {
    if (rule.regex.test(text)) return category(rule.category);
  }
  return null;
}

function explicitTitleCategory(event) {
  const title = foldPublicCategoryText(event?.title);
  if (!title) return null;
  if (SUMMER_PROGRAM_RE.test(title) || isSummerProgram(event)) return category("cursos-talleres-campus");
  return categoryFromRules(title, EXPLICIT_TITLE_RULES);
}

function inferCultureCategory(event) {
  const explicit = explicitTitleCategory(event);
  if (explicit) return explicit;
  return categoryFromRules(evidenceText(event), CULTURE_EVIDENCE_RULES)
    || category(PUBLIC_CATEGORY_TAXONOMY.fallback_category);
}

export function resolvePublicCategory(event) {
  const source = sourceCategory(event);
  const canonical = canonicalPublicCategory(source);
  const explicit = explicitTitleCategory(event);
  const fallbackId = PUBLIC_CATEGORY_TAXONOMY.fallback_category;

  if (canonical && canonical.id !== source.id) return canonical;
  if (isSummerProgram(event)) return category("cursos-talleres-campus");
  // "Otros" is a fallback, not semantic authority. A strong title-level signal
  // must be allowed to recover a more specific shared category after merges.
  if (canonical?.id === fallbackId && explicit && explicit.id !== fallbackId) return explicit;
  if (canonical && PUBLIC_CATEGORIES[canonical.id]) return canonical;
  if (source.id === "cultura" || foldPublicCategoryText(source.label) === "cultura") return inferCultureCategory(event);
  if (!source.id && !source.label) return explicit || category(fallbackId);

  // Source-specific categories remain visible only when they are explicitly
  // registered by the shared architecture contract. They are not redefined
  // inside a city adapter.
  return source;
}
