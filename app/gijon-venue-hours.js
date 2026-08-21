import { EVENT_LOCATION_OVERRIDES } from "./venue-registry.generated.mjs?v=20260820-venues1";
import { venueRecordForEvent } from "./venue-identity.mjs?v=20260820-venues1";

const OVERRIDES = new Map((EVENT_LOCATION_OVERRIDES || []).map((row) => [
  String(row?.official_url || "").replace(/\/$/, ""),
  row,
]).filter(([url]) => url));

const MONTHS = Object.freeze({
  ene: 1, enero: 1, feb: 2, febrero: 2, marzo: 3, abr: 4, abril: 4,
  may: 5, mayo: 5, jun: 6, junio: 6, jul: 7, julio: 7, ago: 8, agosto: 8,
  sep: 9, sept: 9, septiembre: 9, oct: 10, octubre: 10, nov: 11, noviembre: 11,
  dic: 12, diciembre: 12,
});
const WEEKDAYS = Object.freeze({ lun: 0, lunes: 0, mar: 1, martes: 1, mie: 2, miercoles: 2, jue: 3, jueves: 3, vie: 4, viernes: 4, sab: 5, sabado: 5, dom: 6, domingo: 6 });
const TIME_RANGE = /\b([0-2]\d:[0-5]\d)\s*[–-]\s*([0-2]\d:[0-5]\d)(?:\s+y\s+([0-2]\d:[0-5]\d)\s*[–-]\s*([0-2]\d:[0-5]\d))?/i;

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[—−]/g, "–")
    .replace(/\s+/g, " ")
    .trim();
}

function explicitRealTime(value) {
  const match = String(value || "").match(/T([0-2]\d:[0-5]\d)/);
  if (!match) return false;
  return !["00:00", "23:59"].includes(match[1]);
}

function hasExplicitEventTime(schedule) {
  if (explicitRealTime(schedule?.start)) return true;
  if (Array.isArray(schedule?.occurrences) && schedule.occurrences.some((item) => explicitRealTime(item?.start))) return true;
  const display = String(schedule?.display_text || "");
  const times = [...display.matchAll(/(?:^|[^\d])([0-2]\d:[0-5]\d)/g)].map((match) => match[1]);
  return times.some((time) => !["00:00", "23:59"].includes(time));
}

function cleanPlaceholderDisplay(schedule) {
  const display = String(schedule?.display_text || "").trim();
  if (!display) return display;
  return display
    .replace(/\s*·\s*(?:00:00|23:59)(?=\s*$)/, "")
    .replace(/\s+/g, " ")
    .trim();
}

function officialEventUrl(event) {
  return String(event?.links?.official || event?.links?.source || "").replace(/\/$/, "");
}

export function gijonLocationForEvent(event) {
  const location = { ...(event?.location || {}) };
  const override = OVERRIDES.get(officialEventUrl(event));
  if (!override) return location;
  return {
    ...location,
    venue_id: override.venue_id || location.venue_id,
    venue: override.venue || location.venue,
    address: override.address || location.address,
    verification: override.verification || location.verification,
  };
}

function registryHoursForEvent(event) {
  const location = gijonLocationForEvent(event);
  const record = venueRecordForEvent({ ...event, location });
  return record?.opening_hours || null;
}

function dateParts(dateKey) {
  const match = String(dateKey || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const weekday = (new Date(Date.UTC(year, month - 1, day, 12)).getUTCDay() + 6) % 7;
  return { year, month, day, weekday };
}

function monthNumber(token) {
  return MONTHS[fold(token).replace(/[^a-z]/g, "")] || null;
}

function inCyclicRange(value, start, end) {
  return start <= end ? start <= value && value <= end : value >= start || value <= end;
}

function monthQualifierMatches(text, parts, { allowShortMarch = false } = {}) {
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

  const monthToken = allowShortMarch
    ? "ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?"
    : "ene(?:ro)?|feb(?:rero)?|marzo|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:t(?:iembre)?)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?";
  const range = value.match(new RegExp(`\\b(${monthToken})\\s*[–-]\\s*(${monthToken})\\b`));
  if (range) return inCyclicRange(parts.month, monthNumber(range[1]), monthNumber(range[2]));

  const tokens = [...value.matchAll(new RegExp(`\\b(${monthToken})\\b`, "g"))].map((match) => monthNumber(match[1])).filter(Boolean);
  if (tokens.length) return tokens.includes(parts.month);
  return null;
}

function weekdayQualifierMatches(text, weekday) {
  const value = fold(text);
  const token = "lun(?:es)?|mar(?:tes)?|mie(?:rcoles)?|jue(?:ves)?|vie(?:rnes)?|sab(?:ado)?|dom(?:ingo)?";
  const range = value.match(new RegExp(`\\b(${token})\\s*[–-]\\s*(${token})\\b`));
  if (range) return inCyclicRange(weekday, WEEKDAYS[fold(range[1]).slice(0, 3)], WEEKDAYS[fold(range[2]).slice(0, 3)]);
  const matches = [...value.matchAll(new RegExp(`\\b(${token})\\b`, "g"))]
    .map((match) => WEEKDAYS[fold(match[1]).slice(0, 3)])
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

function dateSpecificHours(display, dateKey) {
  const parts = dateParts(dateKey);
  if (!parts) return null;
  const whole = fold(display);
  if (!whole) return null;

  if (parts.weekday === 0) {
    if (/lunes cerrado/.test(whole)) return "Cerrado";
    if (/habitualmente mar[–-]dom/.test(whole) && !(/lunes tambien abre en julio y agosto/.test(whole) && [7, 8].includes(parts.month))) {
      return "Cerrado";
    }
  }

  const chunks = String(display || "")
    .replace(/\.\s+(?=[A-ZÁÉÍÓÚÑ0-9])/g, " · ")
    .split(/\s*·\s*/)
    .map((item) => item.trim())
    .filter(Boolean);

  let activeSeason = true;
  for (const chunk of chunks) {
    const time = rangeLabel(chunk);
    const explicitMonth = monthQualifierMatches(chunk, parts, { allowShortMarch: !time });
    if (!time && explicitMonth !== null) {
      activeSeason = explicitMonth;
      continue;
    }
    if (!time) continue;

    const monthMatch = monthQualifierMatches(chunk, parts, { allowShortMarch: false });
    const appliesSeason = monthMatch === null ? activeSeason : monthMatch;
    if (!appliesSeason) continue;
    const appliesWeekday = weekdayQualifierMatches(chunk, parts.weekday);
    if (appliesWeekday === false) continue;
    return time;
  }
  return null;
}

export function scheduleForGijonEvent(event) {
  const schedule = event?.schedule;
  if (!schedule || typeof schedule !== "object" || hasExplicitEventTime(schedule)) return schedule;

  const next = { ...schedule, display_text: cleanPlaceholderDisplay(schedule) };
  const venue = registryHoursForEvent(event);
  if (!venue?.display) return next;

  next.opening_hours = {
    mode: "venue",
    display_text: venue.display,
    source_name: venue.source_name || "Horario oficial del recinto",
    source_url: venue.source_url || null,
    verified_at: venue.verified_at || null,
  };
  next.hours_confidence = "official_venue_registry";
  return next;
}

export function gijonVenueHours(event) {
  const venue = registryHoursForEvent(event);
  if (!venue?.display) return null;
  return {
    display: venue.display,
    source: venue.source_url || null,
    source_name: venue.source_name || null,
    verified_at: venue.verified_at || null,
  };
}

export function gijonVenueHoursForDate(event, referenceDateKey) {
  const venue = registryHoursForEvent(event);
  if (!venue?.display) return null;
  const display = dateSpecificHours(venue.display, referenceDateKey);
  if (!display) return null;
  return {
    display,
    source: venue.source_url || null,
    source_name: venue.source_name || null,
    verified_at: venue.verified_at || null,
    reference_date: referenceDateKey,
  };
}

export { dateSpecificHours };
