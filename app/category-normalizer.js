import { buildEventSemantics } from "./event-semantics.mjs?v=20260823-semantic-v1";

export function normalizeAgendaCategories(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const normalizedEvents = dataset.events.map((event) => {
    const semantics = buildEventSemantics(event);
    const category = semantics.category;
    return {
      ...event,
      semantics,
      primary_category: category,
      categories: [category],
    };
  });
  return { ...dataset, events: normalizedEvents };
}
