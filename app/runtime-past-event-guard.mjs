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
  return {
    ...dataset,
    events: dataset.events.filter((event) => eventIsCurrentOrFuture(event, { now, timeZone })),
  };
}
