export const PUBLIC_EVENT_CORRECTION_RULES = Object.freeze([
  Object.freeze({
    id: "official-program-category-los-fantasmas",
    cityId: "valparaiso",
    match: Object.freeze({ eventId: "agenda_bc147abef119a17edb8a9770" }),
    ensureCategories: Object.freeze([Object.freeze({ id: "teatro", label: "Teatro" })]),
    authority: "official_program",
  }),
]);

function matchesRule(event, rule, cityId) {
  if (rule?.cityId && String(rule.cityId) !== String(cityId || "")) return false;
  if (rule?.match?.eventId && String(event?.id || "") !== String(rule.match.eventId)) return false;
  if (rule?.match?.sourceId && String(event?.source_id || "") !== String(rule.match.sourceId)) return false;
  return true;
}

function applyRule(event, rule) {
  const categories = Array.isArray(event?.categories) ? [...event.categories] : [];
  let changed = false;
  for (const category of rule.ensureCategories || []) {
    if (categories.some((candidate) => candidate?.id === category.id)) continue;
    categories.push({ ...category });
    changed = true;
  }
  if (!changed) return event;
  const appliedRules = new Set([...(event?.editorial?.applied_correction_rules || []), rule.id]);
  return {
    ...event,
    categories,
    editorial: {
      ...(event?.editorial || {}),
      applied_correction_rules: [...appliedRules],
      correction_authority: rule.authority || "declared_rule",
    },
  };
}

export function applyDeclarativeEventCorrectionRules(dataset, {
  cityId = "",
  rules = PUBLIC_EVENT_CORRECTION_RULES,
} = {}) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    let corrected = event;
    for (const rule of rules) {
      if (matchesRule(corrected, rule, cityId)) corrected = applyRule(corrected, rule);
    }
    if (corrected !== event) changed = true;
    return corrected;
  });
  return changed ? { ...dataset, events } : dataset;
}
