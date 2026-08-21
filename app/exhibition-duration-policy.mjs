export const LONG_EXHIBITION_DAYS = 7;

function dateKeyForValue(value, city) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  if (Number.isNaN(date.getTime()) || !city?.timezone) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: city.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function scheduleWindows(event) {
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

export function exhibitionDurationDays(event, city) {
  const ranges = scheduleWindows(event)
    .map((window) => ({
      start: dateKeyForValue(window.start, city),
      end: dateKeyForValue(window.end, city),
    }))
    .filter((range) => range.start && range.end);
  if (!ranges.length) return null;

  const start = ranges.reduce(
    (value, range) => value < range.start ? value : range.start,
    ranges[0].start,
  );
  const end = ranges.reduce(
    (value, range) => value > range.end ? value : range.end,
    ranges[0].end,
  );
  const startTime = Date.parse(`${start}T12:00:00Z`);
  const endTime = Date.parse(`${end}T12:00:00Z`);
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) return null;
  return (endTime - startTime) / 86400000;
}

export function isLongExhibitionDuration(event, city) {
  const days = exhibitionDurationDays(event, city);
  return Number.isFinite(days) && days > LONG_EXHIBITION_DAYS;
}

export function partitionExhibitionsByDuration(events, city) {
  const regular = [];
  const long = [];
  for (const event of events || []) {
    (isLongExhibitionDuration(event, city) ? long : regular).push(event);
  }
  return { regular, long };
}
