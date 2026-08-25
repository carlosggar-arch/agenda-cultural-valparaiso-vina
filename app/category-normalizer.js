import { buildEventSemantics } from "./event-semantics.mjs?v=20260823-semantic-v1";

export function normalizeEventCategory(event) {
  if (!event || typeof event !== "object") return event;
  const semantics = buildEventSemantics(event);
  const category = semantics.category;
  return {
    ...event,
    semantics,
    primary_category: category,
    categories: [category],
  };
}

export function normalizeAgendaCategories(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  return {
    ...dataset,
    events: dataset.events.map((event) => normalizeEventCategory(event)),
  };
}
