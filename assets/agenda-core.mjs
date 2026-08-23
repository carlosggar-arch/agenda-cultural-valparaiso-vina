import * as base from "./agenda-core-base.mjs?v=20260823-selection1";

export * from "./agenda-core-base.mjs?v=20260823-selection1";

const ROOT_TIME_ZONE = base.DISPLAY_TIME_ZONE || "America/Santiago";

function localDateKey(value, timeZone = ROOT_TIME_ZONE) {
  const text = String(value || "").trim();
  if (!text) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  const year = get("year");
  const month = get("month");
  const day = get("day");
  return year && month && day ? `${year}-${month}-${day}` : null;
}

function finalScheduleValues(event) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.length) {
    return occurrences.map((occurrence) => occurrence?.end || occurrence?.start).filter(Boolean);
  }
  const end = event?.schedule?.end || event?.schedule?.start;
  return end ? [end] : [];
}

export function eventIsCurrentOrFuture(event, now = new Date(), timeZone = ROOT_TIME_ZONE) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return true;
  const today = localDateKey(now, timeZone);
  if (!today) return true;
  const endDates = finalScheduleValues(event)
    .map((value) => localDateKey(value, timeZone))
    .filter(Boolean);
  if (!endDates.length) return true;
  return endDates.some((endDate) => endDate >= today);
}

export async function fetchDataset(fetchImplementation = globalThis.fetch, path = base.DATASET_PATH) {
  let response;
  try {
    response = await fetchImplementation(path, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch (error) {
    throw new base.AgendaDataError(
      "No fue posible conectar con el archivo público de la agenda.",
      "load",
      { cause: error },
    );
  }
  if (!response || !response.ok) {
    throw new base.AgendaDataError(
      `No fue posible cargar la agenda${response ? ` (HTTP ${response.status})` : ""}.`,
      "load",
    );
  }
  let data;
  try {
    data = await response.json();
  } catch (error) {
    throw new base.AgendaDataError(
      "El archivo de agenda no contiene JSON válido.",
      "load",
      { cause: error },
    );
  }
  const validated = base.validateDataset(data);
  const now = new Date();
  return {
    ...validated,
    events: validated.events.filter((event) => eventIsCurrentOrFuture(event, now)),
  };
}

export function eventsForSection(events, sectionId, now = new Date()) {
  return (events || []).filter(
    (event) => eventIsCurrentOrFuture(event, now) && base.eventMatchesSection(event, sectionId, now),
  );
}

export function sectionCounts(events, now = new Date()) {
  return Object.fromEntries(
    base.AGENDA_SECTIONS.map(({ id }) => [id, eventsForSection(events, id, now).length]),
  );
}

export function filterEvents(events, filters = base.defaultFilterState(), now = new Date()) {
  return base.filterEvents(
    (events || []).filter((event) => eventIsCurrentOrFuture(event, now)),
    filters,
    now,
  );
}
