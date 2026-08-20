const ARTEQUIN_NATURAL_ART_EVENT_ID = "agenda_650e95f9b205b8665b0bce6d";
const TITLE_PATTERN = /\bel arte es natural\b/i;

const OFFICIAL_OCCURRENCES = Object.freeze([
  Object.freeze({ start: "2026-08-07T15:00:00-04:00", end: "2026-08-07T16:00:00-04:00" }),
  Object.freeze({ start: "2026-08-14T15:00:00-04:00", end: "2026-08-14T16:00:00-04:00" }),
  Object.freeze({ start: "2026-08-21T15:00:00-04:00", end: "2026-08-21T16:00:00-04:00" }),
  Object.freeze({ start: "2026-08-28T15:00:00-04:00", end: "2026-08-28T16:00:00-04:00" }),
]);

function isTarget(event) {
  if (!event || typeof event !== "object") return false;
  if (String(event.id || "") === ARTEQUIN_NATURAL_ART_EVENT_ID) return true;
  const source = `${event.source_id || ""} ${event.source_name || ""} ${event.location?.venue || ""}`.toLocaleLowerCase("es");
  return source.includes("artequin") && TITLE_PATTERN.test(String(event.title || ""));
}

function correctEvent(event) {
  if (!isTarget(event)) return event;
  const occurrences = OFFICIAL_OCCURRENCES.map((item) => ({ ...item }));
  return {
    ...event,
    schedule: {
      ...(event.schedule || {}),
      mode: "multi_session",
      start: occurrences[0].start,
      end: occurrences[occurrences.length - 1].end,
      timezone: "America/Santiago",
      display_text: "Viernes 7, 14, 21 y 28 ago · 15:00–16:00",
      occurrences,
      recurrence: ["Viernes 7, 14, 21 y 28 de agosto"],
      start_confidence: "official_municipal_listing",
      end_confidence: "official_municipal_listing",
    },
    editorial: {
      ...(event.editorial || {}),
      schedule_correction: "official_visitavina_artequin_four_sessions",
      schedule_correction_source: "https://visitavina.munivina.cl/actividades/",
    },
  };
}

export function correctArtequinNaturalArtSessions(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    const corrected = correctEvent(event);
    if (corrected !== event) changed = true;
    return corrected;
  });
  return changed ? { ...dataset, events } : dataset;
}
