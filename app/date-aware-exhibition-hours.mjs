function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function validClock(value) {
  const text = clean(value);
  return /^([01]\d|2[0-3]):[0-5]\d$/.test(text) ? text : null;
}

export function dateKeyForTimezone(value, timezone = "UTC") {
  if (!value) return null;
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function mondayZeroWeekday(dateKey) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(dateKey || ""))) return null;
  const [year, month, day] = dateKey.split("-").map(Number);
  const sundayZero = new Date(Date.UTC(year, month - 1, day, 12)).getUTCDay();
  return (sundayZero + 6) % 7;
}

function addDateDays(dateKey, days) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(dateKey || "")) || !Number.isInteger(days)) return null;
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days, 12)).toISOString().slice(0, 10);
}

function scheduleBoundaryKeys(schedule, timezone) {
  const start = schedule?.start || schedule?.occurrences?.[0]?.start;
  const end = schedule?.end || schedule?.occurrences?.at?.(-1)?.end || schedule?.occurrences?.at?.(-1)?.start || start;
  return {
    startKey: dateKeyForTimezone(start, timezone),
    endKey: dateKeyForTimezone(end, timezone),
  };
}

function canonicalVenueHours(schedule) {
  const canonical = schedule?.venue_hours;
  if (canonical && typeof canonical === "object" && !Array.isArray(canonical)) return canonical;
  const legacy = schedule?.opening_hours;
  return legacy && typeof legacy === "object" && !Array.isArray(legacy) ? legacy : null;
}

export function exhibitionReferenceDateKey(schedule, options = {}) {
  const timezone = options.timezone || "UTC";
  const requested = dateKeyForTimezone(options.referenceDate || options.now || new Date(), timezone);
  const { startKey, endKey: rawEndKey } = scheduleBoundaryKeys(schedule, timezone);
  const endKey = rawEndKey || startKey;

  if (requested && (!startKey || !endKey || (startKey <= requested && requested <= endKey))) return requested;
  return startKey || requested;
}

function scheduleRange(schedule) {
  const weekly = canonicalVenueHours(schedule);
  const opening = validClock(schedule?.opening_time || weekly?.opening_time);
  const closing = validClock(schedule?.closing_time || weekly?.closing_time);
  return opening && closing && opening !== closing ? `${opening}–${closing}` : null;
}

export function dailyExhibitionHours(schedule, options = {}) {
  if (!schedule || typeof schedule !== "object") return null;
  const referenceDateKey = exhibitionReferenceDateKey(schedule, options);
  if (!referenceDateKey) return null;

  const weekly = canonicalVenueHours(schedule);
  const weekdays = Array.isArray(weekly?.open_weekdays)
    ? weekly.open_weekdays.map(Number).filter((value) => Number.isInteger(value) && value >= 0 && value <= 6)
    : null;

  if (weekdays?.length) {
    const weekday = mondayZeroWeekday(referenceDateKey);
    if (weekday !== null && !weekdays.includes(weekday)) {
      return { label: "Cerrado", closed: true, referenceDateKey, source: "open_weekdays" };
    }
  }

  const label = scheduleRange(schedule);
  if (label) return { label, closed: false, referenceDateKey, source: weekly ? "venue_hours" : "event" };

  // A free-form weekly/seasonal string can contain hours for several different
  // days. Do not repeat it on a date-specific card because it may describe a
  // different day than the one currently being viewed.
  return null;
}

export function nextDailyExhibitionOpening(schedule, options = {}) {
  if (!schedule || typeof schedule !== "object") return null;
  const timezone = options.timezone || "UTC";
  const requested = dateKeyForTimezone(options.referenceDate || options.now || new Date(), timezone);
  if (!requested) return null;
  const { startKey, endKey } = scheduleBoundaryKeys(schedule, timezone);
  const maxDays = Math.max(1, Math.min(14, Number(options.maxDays) || 7));

  for (let daysAhead = 1; daysAhead <= maxDays; daysAhead += 1) {
    const candidate = addDateDays(requested, daysAhead);
    if (!candidate) break;
    if (startKey && candidate < startKey) continue;
    if (endKey && candidate > endKey) break;
    const daily = dailyExhibitionHours(schedule, {
      ...options,
      timezone,
      referenceDate: candidate,
    });
    if (!daily?.label || daily.closed || /^cerrado\b/i.test(daily.label)) continue;
    return { ...daily, daysAhead };
  }
  return null;
}

export function isSameLocalDate(value, dateKey, timezone = "UTC") {
  return Boolean(dateKey && dateKeyForTimezone(value, timezone) === dateKey);
}
