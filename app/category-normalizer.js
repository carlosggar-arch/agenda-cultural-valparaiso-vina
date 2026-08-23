import { resolvePublicCategory } from "./public-category-rules.mjs?v=20260823-taxonomy-v2";

function categoryForEvent(event) {
  return resolvePublicCategory(event);
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
