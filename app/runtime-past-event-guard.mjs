function dateKeyForDate(value, timeZone) {
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

function dateKeyForValue(value, timeZone) {
  const text = String(value || "").trim();
  if (!text) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  return dateKeyForDate(text, timeZone);
}

function datedWindows(event) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.length) {
    return occurrences.map((occurrence) => ({
      start: occurrence?.start,
      end: occurrence?.end || occurrence?.start,
    }));
  }
  if (event?.schedule?.start) {
    return [{
      start: event.schedule.start,
      end: event.schedule.end || event.schedule.start,
    }];
  }
  return [];
}

function pruneExpiredOccurrences(event, { today, timeZone }) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return event;
  const schedule = event?.schedule;
  const occurrences = schedule?.occurrences;
  if (!Array.isArray(occurrences) || !occurrences.length) return event;

  const currentOrFuture = occurrences.filter((occurrence) => {
    const end = dateKeyForValue(occurrence?.end || occurrence?.start, timeZone);
    return !end || end >= today;
  });
  if (!currentOrFuture.length) return null;
  if (currentOrFuture.length === occurrences.length) return event;

  const first = currentOrFuture[0];
  const last = currentOrFuture[currentOrFuture.length - 1];
  return {
    ...event,
    schedule: {
      ...schedule,
      start: first?.start || schedule.start,
      end: last?.end || last?.start || first?.end || first?.start || schedule.end,
      occurrences: currentOrFuture,
      // The original display text may contain already-expired sessions. Let the
      // presentation formatter rebuild a clean label from the remaining dates.
      display_text: null,
    },
  };
}

export function eventIsCurrentOrFuture(event, {
  now = new Date(),
  timeZone = "UTC",
} = {}) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return true;
  const today = dateKeyForDate(now, timeZone);
  if (!today) return true;
  const windows = datedWindows(event);
  if (!windows.length) return true;

  const endKeys = windows
    .map((window) => dateKeyForValue(window.end || window.start, timeZone))
    .filter(Boolean);
  if (!endKeys.length) return true;
  return endKeys.some((end) => end >= today);
}

export function removeExpiredDatedEvents(dataset, {
  now = new Date(),
  timeZone = dataset?.timezone || "UTC",
} = {}) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const today = dateKeyForDate(now, timeZone);
  if (!today) return dataset;

  const events = dataset.events
    .map((event) => pruneExpiredOccurrences(event, { today, timeZone }))
    .filter(Boolean)
    .filter((event) => eventIsCurrentOrFuture(event, { now, timeZone }));

  return { ...dataset, events };
}
