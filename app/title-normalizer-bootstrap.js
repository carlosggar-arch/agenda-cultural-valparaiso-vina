import { normalizePublicEventTitle } from "./public-title-normalizer.mjs?v=20260821-title7";

export function normalizeAgendaTitles(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  return {
    ...dataset,
    events: dataset.events.map((event) => {
      const rawTitle = event?.title == null ? "" : String(event.title);
      const title = normalizePublicEventTitle(rawTitle, event) || rawTitle || "Actividad sin título";
      const normalized = { ...event, title };
      if (
        event
        && !Object.prototype.hasOwnProperty.call(event, "original_title")
        && rawTitle
        && title !== rawTitle
      ) {
        normalized.original_title = rawTitle;
      }
      return normalized;
    }),
  };
}
