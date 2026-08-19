const UNRELIABLE_CONFIDENCE = new Set([
  "technical_fallback",
  "unknown",
  "inferred",
  "estimated",
  "synthetic",
  "fallback",
]);

const START_BOUNDARY_FILTERS = new Set([
  "hoy",
  "manana",
  "fin-de-semana",
  "7-dias",
]);

function normalizeConfidence(value) {
  return String(value ?? "").trim().toLocaleLowerCase("en");
}

export function confidenceIsReliable(value) {
  const normalized = normalizeConfidence(value);
  return Boolean(normalized) && !UNRELIABLE_CONFIDENCE.has(normalized);
}

export function startIsReliable(event) {
  return confidenceIsReliable(event?.schedule?.start_confidence);
}

export function endIsReliable(event) {
  return Boolean(event?.schedule?.end) && confidenceIsReliable(event?.schedule?.end_confidence);
}

export function dateKeyForDate(value, city) {
  const date = value instanceof Date ? value : new Date(value);
  if (!city?.timezone || Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: city.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function dateKeyForValue(value, city) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : dateKeyForDate(date, city);
}

export function addDays(dateKey, days) {
  const date = new Date(`${dateKey}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
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

export function eventDateRanges(event, city) {
  return scheduleWindows(event)
    .map((window) => ({
      start: dateKeyForValue(window.start, city),
      end: dateKeyForValue(window.end, city),
      rawStart: window.start,
      rawEnd: window.end,
    }))
    .filter((range) => range.start && range.end)
    .sort((a, b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end));
}

export function isExhibitionLike(event) {
  const values = [
    event?.primary_category?.id,
    event?.primary_category?.label,
    ...(event?.categories || []).flatMap((category) => [category?.id, category?.label]),
  ].filter(Boolean).join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
  return /exposicion|muestra|museo|artes[- ]visuales/.test(values);
}

function dayNumber(key) {
  return Date.parse(`${key}T12:00:00Z`) / 86400000;
}

function firstRelevantRange(event, city, today) {
  const ranges = eventDateRanges(event, city);
  const active = ranges.find((range) => range.start <= today && range.end >= today);
  if (active) return { range: active, active: true, ranges };
  const upcoming = ranges.find((range) => range.end >= today);
  return { range: upcoming || null, active: false, ranges };
}

export function classifyTemporalEvent(event, city, now = new Date()) {
  const today = dateKeyForDate(now, city);
  if (!today) return null;
  const relevant = firstRelevantRange(event, city, today);
  if (!relevant.range) return {
    today,
    range: null,
    active: false,
    ended: true,
    startReliable: startIsReliable(event),
    endReliable: endIsReliable(event),
    exhibition: isExhibitionLike(event),
    scheduleEnd: null,
    daysUntilStart: null,
    daysUntilEnd: null,
  };
  const scheduleEnd = dateKeyForValue(event?.schedule?.end, city);
  return {
    today,
    range: relevant.range,
    active: relevant.active,
    ended: false,
    startReliable: startIsReliable(event),
    endReliable: endIsReliable(event),
    exhibition: isExhibitionLike(event),
    scheduleEnd,
    daysUntilStart: dayNumber(relevant.range.start) - dayNumber(today),
    daysUntilEnd: scheduleEnd ? dayNumber(scheduleEnd) - dayNumber(today) : null,
  };
}

export function temporalBadge(event, city, now = new Date()) {
  const state = classifyTemporalEvent(event, city, now);
  if (!state || state.ended || !state.range) return null;
  if (state.startReliable && state.range.start === state.today) return "Hoy";
  if (state.endReliable && state.scheduleEnd === state.today) return "Último día";
  if (state.endReliable && state.active && state.daysUntilEnd > 0 && state.daysUntilEnd <= 3) {
    return "Últimos 3 días";
  }
  if (state.endReliable && state.active && state.daysUntilEnd > 3 && state.daysUntilEnd <= 7) {
    return "Última semana";
  }
  return null;
}

function eventTimeSortValue(event, city) {
  const values = [
    ...(event?.schedule?.occurrences || []).map((occurrence) => occurrence?.start),
    event?.schedule?.start,
  ].filter(Boolean);
  for (const value of values) {
    const text = String(value);
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return Date.parse(`${text}T12:00:00Z`);
    const parsed = Date.parse(text);
    if (Number.isFinite(parsed)) return parsed;
  }
  const range = eventDateRanges(event, city)[0];
  return range ? Date.parse(`${range.start}T12:00:00Z`) : Number.POSITIVE_INFINITY;
}

function byTitle(a, b, city) {
  return String(a?.title || "").localeCompare(String(b?.title || ""), city?.locale || "es");
}

export function organizeTemporalPriority(events, city, now = new Date()) {
  const blocks = { today: [], endingSoon: [], upcoming: [], exhibitions: [] };
  for (const event of events || []) {
    if (["program", "flexible_offer"].includes(event?.event_type)) continue;
    const state = classifyTemporalEvent(event, city, now);
    if (!state || state.ended || !state.range) continue;

    if (
      (state.startReliable && state.range.start === state.today)
      || (state.endReliable && state.scheduleEnd === state.today)
    ) {
      blocks.today.push(event);
    } else if (
      state.active
      && state.endReliable
      && state.daysUntilEnd > 0
      && state.daysUntilEnd <= 7
    ) {
      blocks.endingSoon.push(event);
    } else if (state.exhibition && state.active) {
      blocks.exhibitions.push(event);
    } else if (!state.exhibition && state.startReliable && state.range.start > state.today) {
      blocks.upcoming.push(event);
    }
  }

  blocks.today.sort((a, b) => eventTimeSortValue(a, city) - eventTimeSortValue(b, city) || byTitle(a, b, city));
  blocks.endingSoon.sort((a, b) => {
    const left = dateKeyForValue(a?.schedule?.end, city) || "9999-12-31";
    const right = dateKeyForValue(b?.schedule?.end, city) || "9999-12-31";
    return left.localeCompare(right) || byTitle(a, b, city);
  });
  blocks.upcoming.sort((a, b) => eventTimeSortValue(a, city) - eventTimeSortValue(b, city) || byTitle(a, b, city));
  blocks.exhibitions.sort((a, b) => {
    const left = dateKeyForValue(a?.schedule?.end, city) || "9999-12-31";
    const right = dateKeyForValue(b?.schedule?.end, city) || "9999-12-31";
    return left.localeCompare(right) || byTitle(a, b, city);
  });
  return blocks;
}

export function shouldSuppressForTemporalFilter(event, when) {
  if (START_BOUNDARY_FILTERS.has(when)) return !startIsReliable(event);
  if (when === "terminan-pronto") return !endIsReliable(event);
  return false;
}
