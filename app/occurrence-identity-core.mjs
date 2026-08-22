export const STRICT_START_TOLERANCE_MINUTES = 5;
export const SCHEDULE_CONFLICT_TOLERANCE_MINUTES = 60;

function unique(values) {
  return [...new Set((values || []).filter(Boolean))];
}

export function localOccurrenceMinute(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return null;
  return Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5])) / 60000;
}

export function localOccurrenceDate(value) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}

export function eventOccurrenceStarts(event) {
  const occurrences = Array.isArray(event?.schedule?.occurrences) ? event.schedule.occurrences : [];
  return occurrences.length
    ? occurrences.map((item) => item?.start).filter(Boolean)
    : [event?.schedule?.start].filter(Boolean);
}

export function timedOccurrenceStarts(event) {
  return eventOccurrenceStarts(event).map(localOccurrenceMinute).filter(Number.isFinite);
}

export function localOccurrenceDates(event) {
  return unique(eventOccurrenceStarts(event).map(localOccurrenceDate).filter(Boolean));
}

export function sameLocalOccurrenceStart(a, b, toleranceMinutes = STRICT_START_TOLERANCE_MINUTES) {
  const startsA = timedOccurrenceStarts(a);
  const startsB = timedOccurrenceStarts(b);
  if (!startsA.length || !startsB.length) return false;
  return startsA.some((left) => startsB.some((right) => Math.abs(left - right) <= toleranceMinutes));
}

export function sameLocalOccurrenceDate(a, b) {
  const datesA = localOccurrenceDates(a);
  const datesB = new Set(localOccurrenceDates(b));
  return datesA.length > 0 && datesA.some((date) => datesB.has(date));
}

export function minimumOccurrenceStartDifferenceMinutes(a, b) {
  const startsA = timedOccurrenceStarts(a);
  const startsB = timedOccurrenceStarts(b);
  if (!startsA.length || !startsB.length) return Number.POSITIVE_INFINITY;
  let minimum = Number.POSITIVE_INFINITY;
  for (const left of startsA) {
    for (const right of startsB) minimum = Math.min(minimum, Math.abs(left - right));
  }
  return minimum;
}
