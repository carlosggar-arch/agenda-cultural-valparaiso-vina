import { canonicalPublicCategory, resolvePublicCategory } from "./public-category-rules.mjs?v=20260821-shared-taxonomy1";

function categoryForEvent(event) {
  const hint = String(event?.editorial?.category_recovery_hint || "").trim();
  return hint ? canonicalPublicCategory(hint) : resolvePublicCategory(event);
}

export function normalizeAgendaCategories(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const normalizedEvents = dataset.events.map((event) => {
    const category = categoryForEvent(event);
    return {
      ...event,
      primary_category: category,
      categories: [category],
    };
  });
  return { ...dataset, events: normalizedEvents };
}
