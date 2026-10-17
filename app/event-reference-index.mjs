import { isExhibitionVisitSchedule } from "../assets/event-schedule-display.mjs";

// Cards consume the canonical events array. Links and saved plans also resolve
// the original visit IDs, using only identities retained by that same model.
export function buildEventReferenceIndex(events) {
  const rows = Array.isArray(events) ? events : [];
  const index = new Map(rows
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));
  for (const event of rows) {
    const visits = event?.editorial?.exhibition_visits;
    if (!isExhibitionVisitSchedule(event?.schedule)
      || visits?.kind !== "same_official_exhibition_dates"
      || !Array.isArray(visits.sources)) continue;
    const retainedIds = new Set(visits.source_event_ids || []);
    for (const source of visits.sources) {
      const id = String(source?.event_id || "").trim();
      if (!id || index.has(id) || !retainedIds.has(id)
        || !source?.schedule?.start || !source?.schedule?.end) continue;
      const links = { ...event.links, official: source.url };
      for (const field of ["source", "presentation_source"]) {
        if (links[field] === event?.links?.official) links[field] = source.url;
      }
      index.set(id, {
        ...event,
        id,
        schedule: { ...source.schedule },
        links,
        source_url: event.source_url === event?.links?.official ? source.url : event.source_url,
      });
    }
  }
  return index;
}
