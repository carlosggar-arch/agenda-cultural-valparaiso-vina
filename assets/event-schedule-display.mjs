const DEFAULTS = Object.freeze({ locale: "es-CL", timezone: "America/Santiago" });

function validTime(value) {
  const match = String(value || "").match(/^([01]\d|2[0-3]):([0-5]\d)$/);
  return match ? match[0] : null;
}

function dateKey(value, timezone) {
  const text = String(value || "");
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

function todayKey(timezone, now = new Date()) {
  return dateKey(now, timezone);
}

function dateObject(value) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    const [year, month, day] = text.split("-").map(Number);
    return new Date(Date.UTC(year, month - 1, day, 12));
  }
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value, { locale, timezone, weekday = true, time = false, year = false }) {
  const date = dateObject(value);
  if (!date) return null;
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""));
  return new Intl.DateTimeFormat(locale, {
    timeZone: dateOnly ? "UTC" : timezone,
    weekday: weekday ? "short" : undefined,
    day: "numeric",
    month: "short",
    year: year ? "numeric" : undefined,
    ...(time && !dateOnly ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(date);
}

function timeFromValue(value, timezone) {
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

function dateRangeLabel(schedule, options) {
  const start = schedule?.start || schedule?.occurrences?.[0]?.start;
  const end = schedule?.end || schedule?.occurrences?.[0]?.end;
  const startKey = dateKey(start, options.timezone);
  const endKey = dateKey(end, options.timezone);
  if (!startKey) return null;
  if (endKey && endKey !== startKey) {
    const first = formatDate(start, { ...options, time: false });
    const last = formatDate(end, { ...options, weekday: false, time: false });
    return first && last ? `${first} – ${last}` : first || last;
  }
  return formatDate(start, { ...options, time: false });
}

function currentOpeningHours(schedule, options) {
  const opening = validTime(schedule?.opening_time);
  const closing = validTime(schedule?.closing_time);
  if (opening && closing && opening !== closing) {
    return { opening, closing, closed: false, source: schedule?.hours_confidence || "event" };
  }

  const weekly = schedule?.opening_hours;
  if (!weekly || typeof weekly !== "object") return null;
  const weeklyOpening = validTime(weekly.opening_time);
  const weeklyClosing = validTime(weekly.closing_time);
  if (!(weeklyOpening && weeklyClosing) || weeklyOpening === weeklyClosing) return null;

  const start = schedule?.start || schedule?.occurrences?.[0]?.start;
  const end = schedule?.end || schedule?.occurrences?.[0]?.end || start;
  const today = todayKey(options.timezone, options.now);
  const startKey = dateKey(start, options.timezone);
  const endKey = dateKey(end, options.timezone);
  const activeToday = today && startKey && endKey && startKey <= today && today <= endKey;
  const referenceClosed = weekly.is_open_on_reference_date === false;

  return {
    opening: weeklyOpening,
    closing: weeklyClosing,
    closed: activeToday && referenceClosed,
    source: "opening_hours",
    regularLabel: String(weekly.display_text || "").trim() || null,
  };
}

export function formatSchedule(schedule, options = {}) {
  if (!schedule || typeof schedule !== "object") return "Horario por confirmar";
  const settings = { ...DEFAULTS, now: new Date(), ...options };
  const visitHours = currentOpeningHours(schedule, settings);
  const range = dateRangeLabel(schedule, settings);

  if (visitHours) {
    if (visitHours.closed) {
      return [range, "Cerrado hoy", visitHours.regularLabel].filter(Boolean).join(" · ");
    }
    return `${range || "Horario de visita"} · ${visitHours.opening}–${visitHours.closing}`;
  }

  const start = schedule.start || schedule.occurrences?.[0]?.start;
  const end = schedule.end || schedule.occurrences?.[0]?.end;
  if (!start) return schedule.display_text || "Horario por confirmar";

  const startKey = dateKey(start, settings.timezone);
  const endKey = dateKey(end, settings.timezone);
  const startTime = timeFromValue(start, settings.timezone);
  const endTime = timeFromValue(end, settings.timezone);

  if (startKey && endKey && startKey === endKey && startTime) {
    const date = formatDate(start, { ...settings, time: false });
    if (endTime && endTime !== startTime) return `${date} · ${startTime}–${endTime}`;
    return `${date} · ${startTime}`;
  }

  if (startKey && endKey && endKey !== startKey) {
    return range || schedule.display_text || "Horario por confirmar";
  }

  return formatDate(start, { ...settings, time: true }) || schedule.display_text || "Horario por confirmar";
}

export function compactScheduleDayLabel(schedule, options = {}) {
  if (!schedule || typeof schedule !== "object") return null;
  const settings = { ...DEFAULTS, now: new Date(), ...options };
  const start = schedule.start || schedule.occurrences?.[0]?.start;
  const end = schedule.end || schedule.occurrences?.[0]?.end || start;
  const startKey = dateKey(start, settings.timezone);
  const endKey = dateKey(end, settings.timezone);
  const today = todayKey(settings.timezone, settings.now);
  if (startKey && endKey && today && startKey <= today && today <= endKey) {
    return { text: "Hoy", today: true };
  }
  if (!startKey) return null;
  const text = formatDate(startKey, { ...settings, weekday: false, time: false });
  return text ? { text, today: false } : null;
}
