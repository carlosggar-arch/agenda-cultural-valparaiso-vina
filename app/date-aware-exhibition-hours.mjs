const MONTHS = Object.freeze({
  ene: 1, enero: 1, feb: 2, febrero: 2, marzo: 3, abr: 4, abril: 4,
  may: 5, mayo: 5, jun: 6, junio: 6, jul: 7, julio: 7, ago: 8, agosto: 8,
  sep: 9, sept: 9, septiembre: 9, oct: 10, octubre: 10, nov: 11, noviembre: 11,
  dic: 12, diciembre: 12,
});
const WEEKDAYS = Object.freeze({
  lun: 0, lunes: 0, mar: 1, martes: 1, mie: 2, miercoles: 2,
  jue: 3, jueves: 3, vie: 4, viernes: 4, sab: 5, sabado: 5,
  dom: 6, domingo: 6,
});
const TIME_RANGE = /\b([0-2]\d:[0-5]\d)\s*[–—-]\s*([0-2]\d:[0-5]\d)(?:\s+y\s+([0-2]\d:[0-5]\d)\s*[–—-]\s*([0-2]\d:[0-5]\d))?/i;
const WEEKDAY_TOKEN = /\b(?:lun(?:es)?|mar(?:tes)?|mie(?:rcoles)?|jue(?:ves)?|vie(?:rnes)?|sab(?:ado)?s?|dom(?:ingo)?s?)\b/i;

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function fold(value) {
  return clean(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[—−]/g, "–");
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

function dateParts(dateKey) {
  const match = String(dateKey || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  return { year, month, day, weekday: mondayZeroWeekday(dateKey) };
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

function normalizedVenueRanges(weekly) {
  const ranges = Array.isArray(weekly?.ranges) ? weekly.ranges : [];
  return ranges.map((range) => {
    const opening = validClock(range?.opening_time);
    const closing = validClock(range?.closing_time);
    return opening && closing && opening !== closing ? `${opening}–${closing}` : null;
  }).filter(Boolean);
}

function scheduleRange(schedule) {
  const weekly = canonicalVenueHours(schedule);
  const ranges = normalizedVenueRanges(weekly);
  if (ranges.length) return ranges.join(" y ");
  const opening = validClock(schedule?.opening_time || weekly?.opening_time);
  const closing = validClock(schedule?.closing_time || weekly?.closing_time);
  return opening && closing && opening !== closing ? `${opening}–${closing}` : null;
}

function monthNumber(token) {
  return MONTHS[fold(token).replace(/[^a-z]/g, "")] || null;
}

function inCyclicRange(value, start, end) {
  if (!(Number.isInteger(start) && Number.isInteger(end))) return false;
  return start <= end ? start <= value && value <= end : value >= start || value <= end;
}

function monthQualifierMatches(text, parts) {
  const value = fold(text);
  if (!value) return null;

  const dated = value.match(/\b(\d{1,2})\s+(ene(?:ro)?|feb(?:rero)?|marzo|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)\s*[–-]\s*(\d{1,2})\s+(ene(?:ro)?|feb(?:rero)?|marzo|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)/);
  if (dated) {
    const startMonth = monthNumber(dated[2]);
    const endMonth = monthNumber(dated[4]);
    const current = parts.month * 100 + parts.day;
    const start = startMonth * 100 + Number(dated[1]);
    const end = endMonth * 100 + Number(dated[3]);
    return start <= end ? start <= current && current <= end : current >= start || current <= end;
  }

  const monthToken = "ene(?:ro)?|feb(?:rero)?|marzo|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?";
  const ranges = [...value.matchAll(new RegExp(`\\b(${monthToken})\\s*[–-]\\s*(${monthToken})\\b`, "g"))]
    .map((match) => [monthNumber(match[1]), monthNumber(match[2])]);
  const tokens = [...value.matchAll(new RegExp(`\\b(${monthToken})\\b`, "g"))]
    .map((match) => monthNumber(match[1])).filter(Boolean);
  if (!ranges.length && !tokens.length) return null;
  return ranges.some(([start, end]) => inCyclicRange(parts.month, start, end)) || tokens.includes(parts.month);
}

function weekdayQualifierMatches(text, weekday) {
  const value = fold(text);
  const token = "lun(?:es)?|mar(?:tes)?|mie(?:rcoles)?|jue(?:ves)?|vie(?:rnes)?|sab(?:ado)?s?|dom(?:ingo)?s?";
  const range = value.match(new RegExp(`\\b(${token})\\s*(?:a|[–-])\\s*(${token})\\b`));
  if (range) {
    const start = WEEKDAYS[fold(range[1]).replace(/s$/, "").slice(0, 3)];
    const end = WEEKDAYS[fold(range[2]).replace(/s$/, "").slice(0, 3)];
    return inCyclicRange(weekday, start, end);
  }
  const matches = [...value.matchAll(new RegExp(`\\b(${token})\\b`, "g"))]
    .map((match) => WEEKDAYS[fold(match[1]).replace(/s$/, "").slice(0, 3)])
    .filter((item) => Number.isInteger(item));
  return matches.length ? matches.includes(weekday) : null;
}

function rangeLabel(text) {
  const match = String(text || "").match(TIME_RANGE);
  if (!match) return null;
  return match[3] && match[4]
    ? `${match[1]}–${match[2]} y ${match[3]}–${match[4]}`
    : `${match[1]}–${match[2]}`;
}

/**
 * Resolve a weekly/seasonal official venue-hours sentence against one concrete
 * calendar date. City adapters may provide the source text, but the shared
 * presentation layer decides what hours are valid for the viewed date.
 */
export function hoursForDateFromDisplay(display, dateKey) {
  const parts = dateParts(dateKey);
  if (!parts) return null;
  const whole = fold(display);
  if (!whole) return null;

  const chunks = String(display || "")
    .replace(/\.\s+(?=[A-ZÁÉÍÓÚÜÑ0-9])/g, " · ")
    .split(/\s*[·;]\s*/)
    .map((item) => item.trim())
    .filter(Boolean);

  for (const chunk of chunks) {
    if (!/cerrad[oa]s?/i.test(fold(chunk))) continue;
    if (weekdayQualifierMatches(chunk, parts.weekday) === true) return "Cerrado";
  }

  let activeSeason = true;
  let sawWeekdayQualifiedHours = false;
  for (const chunk of chunks) {
    const time = rangeLabel(chunk);
    const explicitMonth = monthQualifierMatches(chunk, parts);
    if (!time && explicitMonth !== null) {
      activeSeason = explicitMonth;
      continue;
    }
    if (!time) continue;

    const monthMatch = monthQualifierMatches(chunk, parts);
    const appliesSeason = monthMatch === null ? activeSeason : monthMatch;
    if (!appliesSeason) continue;

    const appliesWeekday = weekdayQualifierMatches(chunk, parts.weekday);
    if (appliesWeekday !== null) sawWeekdayQualifiedHours = true;
    if (appliesWeekday === false) continue;
    return time;
  }

  if (sawWeekdayQualifiedHours || WEEKDAY_TOKEN.test(whole)) return "Cerrado";
  return null;
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

  const freeform = clean(weekly?.display_text || schedule?.venue_opening_hours || schedule?.visit_hours);
  const resolved = hoursForDateFromDisplay(freeform, referenceDateKey);
  if (resolved) {
    const closed = /^cerrado\b/i.test(resolved);
    return { label: resolved, closed, referenceDateKey, source: "venue_hours_date_resolved" };
  }

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
