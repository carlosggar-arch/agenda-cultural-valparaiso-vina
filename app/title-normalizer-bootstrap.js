import { normalizePublicEventTitle } from "./public-title-normalizer.mjs?v=20260818-title3";

export function normalizeAgendaTitles(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  return {
    ...dataset,
    events: dataset.events.map((event) => ({
      ...event,
      title: normalizePublicEventTitle(event?.title || "", event) || event?.title || "Actividad sin título",
    })),
  };
}
