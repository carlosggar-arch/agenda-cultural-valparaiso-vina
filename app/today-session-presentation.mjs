const DEFAULTS = Object.freeze({ locale: "es-CL", timezone: "America/Santiago" });
export const MISSING_EVENT_TIME_LABEL = "Consultar horario en la fuente";

const MONTHS = Object.freeze({
  enero: 1,
  febrero: 2,
  marzo: 3,
  abril: 4,
  mayo: 5,
  junio: 6,
  julio: 7,
  agosto: 8,
  septiembre: 9,
  setiembre: 9,
  octubre: 10,
  noviembre: 11,
  diciembre: 12,
});

const SHORT_MONTHS = Object.freeze({
  ene: 1,
  feb: 2,
  mar: 3,
  abr: 4,
  may: 5,
  jun: 6,
  jul: 7,
  ago: 8,
  sep: 9,
  sept: 9,
  oct: 10,
  nov: 11,
  dic: 12,
});

function dateKey(value, timezone) {
  const text = String(value || "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
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

function localClock(value, timezone) {
  if (!String(value || "").includes("T")) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(date);
}

function validClock(value) {
  const text = String(value || "").trim();
  return /^([01]\d|2[0-3]):[0-5]\d$/.test(text) ? text : null;
}

function dateFromParts(year, month, day) {
  const y = Number(year);
  const m = Number(month);
  const d = Number(day);
  if (!Number.isInteger(y) || !Number.isInteger(m) || !Number.isInteger(d)) return null;
  if (y < 2000 || y > 2100 || m < 1 || m > 12 || d < 1 || d > 31) return null;
  const key = `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  const probe = new Date(`${key}T12:00:00Z`);
  if (Number.isNaN(probe.getTime()) || probe.toISOString().slice(0, 10) !== key) return null;
  return key;
}

function addSession(target, key, time) {
  const clock = validClock(time);
  if (!key || !clock) return;
  const id = `${key}|${clock}`;
  if (!target.some((item) => item.id === id)) target.push({ id, key, time: clock });
}

function inferredYear(event, timezone) {
  const start = dateKey(event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start, timezone);
  const year = Number(String(start || "").slice(0, 4));
  return Number.isInteger(year) && year >= 2000 ? year : new Date().getUTCFullYear();
}

function structuredSessions(event, options) {
  const sessions = [];
  for (const occurrence of event?.schedule?.occurrences || []) {
    const key = dateKey(occurrence?.start, options.timezone);
    const time = localClock(occurrence?.start, options.timezone);
    addSession(sessions, key, time);
  }
  return sessions;
}

function canonicalFlatSessions(event, options, referenceDate) {
  const schedule = event?.schedule || {};
  if ((schedule.occurrences || []).length) return [];
  const times = Array.isArray(schedule.session_times) ? schedule.session_times.map(validClock).filter(Boolean) : [];
  if (!times.length) return [];

  // A flat session list can only be attached safely to a date when the event is
  // itself single-day. Multi-day session dates remain represented by occurrences
  // (or the legacy dated-list fallback below) rather than being guessed.
  const startKey = dateKey(schedule.start, options.timezone);
  const endKey = dateKey(schedule.end || schedule.start, options.timezone);
  if (!(referenceDate && startKey === referenceDate && (!endKey || endKey === startKey))) return [];

  const sessions = [];
  for (const time of times) addSession(sessions, referenceDate, time);
  return sessions;
}

function listedSessions(event, options) {
  const description = String(event?.description || "").replace(/\s+/g, " ").trim();
  const display = String(event?.schedule?.display_text || "").replace(/\s+/g, " ").trim();
  const marker = description.match(/\b(?:funciones?|sesiones?|horarios?)\s*:\s*/iu);
  const text = [marker ? description.slice(marker.index + marker[0].length) : "", display].filter(Boolean).join(" ; ");
  if (!text) return [];

  const sessions = [];
  const baseYear = inferredYear(event, options.timezone);

  const longDate = /(?:\b(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+)?(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+de\s+(20\d{2}))?\s*[,·-]?\s*(\d{1,2}):([0-5]\d)\s*(?:h|hrs?|horas?)?/giu;
  for (const match of text.matchAll(longDate)) {
    const month = MONTHS[match[2].toLocaleLowerCase("es")];
    const key = dateFromParts(match[3] || baseYear, month, match[1]);
    addSession(sessions, key, `${String(match[4]).padStart(2, "0")}:${match[5]}`);
  }

  const isoDate = /\b(20\d{2})-(\d{2})-(\d{2})\s*(?:[·,;-]\s*)?(\d{1,2}):([0-5]\d)\b/g;
  for (const match of text.matchAll(isoDate)) {
    const key = dateFromParts(match[1], match[2], match[3]);
    addSession(sessions, key, `${String(match[4]).padStart(2, "0")}:${match[5]}`);
  }

  const shortDate = /\b(\d{1,2})\s+(ene|feb|mar|abr|may|jun|jul|ago|sep|sept|oct|nov|dic)\.?\s*(?:[·,;-]\s*)?(\d{1,2}):([0-5]\d)\b/giu;
  for (const match of text.matchAll(shortDate)) {
    const month = SHORT_MONTHS[match[2].toLocaleLowerCase("es")];
    const key = dateFromParts(baseYear, month, match[1]);
    addSession(sessions, key, `${String(match[3]).padStart(2, "0")}:${match[4]}`);
  }

  return sessions;
}

function formatDateKey(key, options) {
  const [year, month, day] = String(key || "").split("-").map(Number);
  if (!(year && month && day)) return null;
  return new Intl.DateTimeFormat(options.locale, {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date(Date.UTC(year, month - 1, day, 12)));
}

export function hasEventSpecificTime(schedule) {
  if (!schedule || typeof schedule !== "object") return false;

  // Once Point 8 has classified the schedule, do not reinterpret legacy
  // display_text (which may contain only museum/venue hours) as an event time.
  if (schedule.schedule_contract_version) {
    if (Array.isArray(schedule.session_times) && schedule.session_times.some(validClock)) return true;
    return (Array.isArray(schedule.occurrences) ? schedule.occurrences : [])
      .some((occurrence) => /T(?:[01]\d|2[0-3]):[0-5]\d/.test(String(occurrence?.start || "")));
  }

  const occurrenceValues = (Array.isArray(schedule.occurrences) ? schedule.occurrences : [])
    .flatMap((occurrence) => [occurrence?.start, occurrence?.end]);
  const structuredValues = [schedule.start, schedule.end, ...occurrenceValues];
  if (structuredValues.some((value) => /T(?:[01]\d|2[0-3]):[0-5]\d/.test(String(value || "")))) return true;
  const display = String(schedule.display_text || "");
  return /(?:^|[^\d])(?:[01]?\d|2[0-3]):[0-5]\d(?:[^\d]|$)/.test(display);
}

export function withMissingEventTimeFallback(formattedSchedule, schedule) {
  const formatted = String(formattedSchedule || "").trim();
  if (hasEventSpecificTime(schedule)) return formatted;
  if (!formatted) return MISSING_EVENT_TIME_LABEL;
  if (formatted.includes(MISSING_EVENT_TIME_LABEL)) return formatted;
  return `${formatted} · ${MISSING_EVENT_TIME_LABEL}`;
}

/**
 * Returns a compact session label for the date currently being viewed. Dated
 * occurrences are authoritative. Legacy dated lists remain a compatibility
 * fallback until every source emits occurrences directly.
 */
export function sessionScheduleLabelForDate(event, options = {}) {
  if (!event || typeof event !== "object") return null;
  const settings = { ...DEFAULTS, now: new Date(), ...options };
  const referenceDate = dateKey(settings.referenceDate || settings.now, settings.timezone);
  if (!referenceDate) return null;

  const sessions = [];
  for (const session of structuredSessions(event, settings)) addSession(sessions, session.key, session.time);
  for (const session of canonicalFlatSessions(event, settings, referenceDate)) addSession(sessions, session.key, session.time);
  for (const session of listedSessions(event, settings)) addSession(sessions, session.key, session.time);

  // Do not reinterpret one ordinary single event as a session list; its normal
  // start/end interval continues through the shared formatter.
  if (sessions.length < 2) return null;

  const times = [...new Set(sessions.filter((item) => item.key === referenceDate).map((item) => item.time))];
  if (!times.length) return null;

  const date = formatDateKey(referenceDate, settings);
  return [date, times.join(", ")].filter(Boolean).join(" · ");
}

export function todaySessionScheduleLabel(event, options = {}) {
  return sessionScheduleLabelForDate(event, {
    ...options,
    referenceDate: options.referenceDate || options.now || new Date(),
  });
}
