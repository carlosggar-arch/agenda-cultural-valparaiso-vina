const DEFAULTS = Object.freeze({ locale: "es-CL", timezone: "America/Santiago" });
const TIME_IN_TEXT = /(?:^|[^\d])(?:[01]?\d|2[0-3]):[0-5]\d(?:\s*(?:h|hrs?))?/i;
const CLOCK_IN_TEXT = /\b(?:[01]\d|2[0-3]):[0-5]\d\b/g;
const TRAILING_DATE_RANGE = /\s[–-]\s(?:\d{4}-\d{2}-\d{2}|\d{1,2}-\d{1,2}-\d{4})\s*$/;
const FOUR_TIME_LIST = /\b(?:[01]\d|2[0-3]):[0-5]\d\s*,\s*(?:[01]\d|2[0-3]):[0-5]\d\s*,\s*(?:[01]\d|2[0-3]):[0-5]\d\s*,\s*(?:[01]\d|2[0-3]):[0-5]\d\b/;
const TWO_TIME_COMMA_LIST = /\b((?:[01]\d|2[0-3]):[0-5]\d)\s*,\s*((?:[01]\d|2[0-3]):[0-5]\d)\b/;

function validTime(value) {
  const match = String(value || "").match(/^([01]\d|2[0-3]):([0-5]\d)$/);
  return match ? match[0] : null;
}

function clockMinutes(value) {
  const clock = validTime(value);
  if (!clock) return null;
  const [hour, minute] = clock.split(":").map(Number);
  return hour * 60 + minute;
}

function displayClocks(value) {
  return String(value || "").match(CLOCK_IN_TEXT) || [];
}

function isAllDayDisplay(value) {
  const clocks = displayClocks(value);
  return clocks.length === 2 && clocks[0] === "00:00" && clocks[1] === "23:59";
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

function occurrenceStartTimes(schedule, options) {
  const occurrences = Array.isArray(schedule?.occurrences) ? schedule.occurrences : [];
  return occurrences
    .map((occurrence) => ({
      start: occurrence?.start,
      key: dateKey(occurrence?.start, options.timezone),
      time: timeFromValue(occurrence?.start, options.timezone),
    }))
    .filter((item) => item.key && item.time);
}

function hasMultipleStructuredSessions(schedule, options) {
  const dated = occurrenceStartTimes(schedule, options);
  return new Set(dated.map((item) => `${item.key}|${item.time}`)).size >= 2;
}

function occurrenceTimesLabel(schedule, options) {
  const dated = occurrenceStartTimes(schedule, options);
  if (dated.length < 2) return null;
  const keys = [...new Set(dated.map((item) => item.key))];
  if (keys.length !== 1) return null;
  const times = [...new Set(dated.map((item) => item.time))];
  if (times.length < 2) return null;
  const date = formatDate(dated[0].start, { ...options, time: false });
  return date ? `${date} · ${times.join(", ")}` : times.join(", ");
}

function simpleTwoTimeInterval(schedule, options) {
  const display = String(schedule?.display_text || "").trim();
  const clocks = displayClocks(display);
  if (clocks.length !== 2 || isAllDayDisplay(display)) return null;
  if (!TWO_TIME_COMMA_LIST.test(display)) return null;
  if (hasMultipleStructuredSessions(schedule, options)) return null;

  const [startClock, endClock] = clocks;
  const startMinutes = clockMinutes(startClock);
  const endMinutes = clockMinutes(endClock);
  if (startMinutes === null || endMinutes === null || startMinutes >= endMinutes) return null;

  const structuredStart = timeFromValue(schedule?.start, options.timezone);
  if (structuredStart && structuredStart !== startClock) return null;

  const range = dateRangeLabel(schedule, options);
  return [range, `${startClock}–${endClock}`].filter(Boolean).join(" · ");
}

function pairedRangeDisplayText(schedule, options) {
  if (schedule?.mode !== "multi_day") return null;
  const display = String(schedule?.display_text || "").trim();
  const list = display.match(FOUR_TIME_LIST)?.[0];
  if (!list) return null;

  const times = list.match(/\b(?:[01]\d|2[0-3]):[0-5]\d\b/g) || [];
  if (times.length !== 4) return null;

  const start = schedule?.start;
  const end = schedule?.end;
  const startKey = dateKey(start, options.timezone);
  const endKey = dateKey(end, options.timezone);
  if (
    !String(start || "").includes("T")
    || !startKey
    || !endKey
    || startKey === endKey
    || timeFromValue(start, options.timezone) !== times[0]
    || hasMultipleStructuredSessions(schedule, options)
  ) return null;

  const firstStart = clockMinutes(times[0]);
  const firstEnd = clockMinutes(times[1]);
  const secondStart = clockMinutes(times[2]);
  const secondEnd = clockMinutes(times[3]);
  if (
    firstStart === null || firstEnd === null || secondStart === null || secondEnd === null
    || firstStart >= firstEnd || secondStart >= secondEnd
  ) return null;

  const range = dateRangeLabel(schedule, options);
  const ranges = `${times[0]}–${times[1]} · ${times[2]}–${times[3]}`;
  return range ? `${range} · ${ranges}` : ranges;
}

function currentOpeningHours(schedule, options) {
  const opening = validTime(schedule?.opening_time);
  const closing = validTime(schedule?.closing_time);
  if (opening && closing && opening !== closing) {
    return { opening, closing, closed: false, source: schedule?.hours_confidence || "event", regularLabel: null };
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

function explicitOpeningHoursLabel(schedule) {
  const weekly = schedule?.opening_hours;
  if (!weekly || typeof weekly !== "object") return null;
  return String(weekly.display_text || "").trim() || null;
}

function timedDisplayText(schedule, timezone) {
  const display = String(schedule?.display_text || "").trim();
  if (!(display && TIME_IN_TEXT.test(display))) return null;
  if (isAllDayDisplay(display)) return null;

  const start = schedule?.start;
  const end = schedule?.end;
  const dateOnlyEnd = /^\d{4}-\d{2}-\d{2}$/.test(String(end || ""));
  if (
    String(start || "").includes("T")
    && dateOnlyEnd
    && dateKey(start, timezone) === String(end)
    && TRAILING_DATE_RANGE.test(display)
  ) {
    return null;
  }
  return display;
}

export function formatSchedule(schedule, options = {}) {
  if (!schedule || typeof schedule !== "object") return "Horario por confirmar";
  const settings = { ...DEFAULTS, now: new Date(), ...options };
  const visitHours = currentOpeningHours(schedule, settings);
  const range = dateRangeLabel(schedule, settings);

  if (visitHours) {
    if (visitHours.closed) {
      return [range, "Cerrado hoy", visitHours.regularLabel || `${visitHours.opening}–${visitHours.closing}`]
        .filter(Boolean)
        .join(" · ");
    }
    return [
      range || "Horario de visita",
      visitHours.regularLabel || `${visitHours.opening}–${visitHours.closing}`,
    ].filter(Boolean).join(" · ");
  }

  const explicitOpeningHours = explicitOpeningHoursLabel(schedule);
  if (explicitOpeningHours) {
    return [range || "Horario de visita", explicitOpeningHours].filter(Boolean).join(" · ");
  }

  const multipleTimes = occurrenceTimesLabel(schedule, settings);
  if (multipleTimes) return multipleTimes;

  const simpleInterval = simpleTwoTimeInterval(schedule, settings);
  if (simpleInterval) return simpleInterval;

  const pairedRanges = pairedRangeDisplayText(schedule, settings);
  if (pairedRanges) return pairedRanges;

  const start = schedule.start || schedule.occurrences?.[0]?.start;
  const end = schedule.end || schedule.occurrences?.[0]?.end;
  const startKey = dateKey(start, settings.timezone);
  const endKey = dateKey(end, settings.timezone);
  const startTime = timeFromValue(start, settings.timezone);
  const endTime = timeFromValue(end, settings.timezone);

  if (startKey && endKey && startKey === endKey && startTime) {
    const date = formatDate(start, { ...settings, time: false });
    if (endTime && endTime !== startTime) return `${date} · ${startTime}–${endTime}`;
    return `${date} · ${startTime}`;
  }

  const explicitDisplay = timedDisplayText(schedule, settings.timezone);
  if (explicitDisplay) return explicitDisplay;

  if (!start) return schedule.display_text || "Horario por confirmar";

  if (startKey && endKey && endKey !== startKey) {
    return range || schedule.display_text || "Horario por confirmar";
  }

  if (startTime) {
    const date = formatDate(start, { ...settings, time: false });
    return date ? `${date} · ${startTime}` : startTime;
  }

  return formatDate(start, { ...settings, time: false }) || schedule.display_text || "Horario por confirmar";
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
