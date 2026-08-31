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

export const CONTENT_KINDS = Object.freeze([
  "dated_event",
  "long_running_event",
  "recurring_offer",
  "permanent_offer",
  "call_for_submissions",
  "undated",
]);

export const TEMPORAL_BUCKETS = Object.freeze([
  "today",
  "this_weekend",
  "ending_soon",
  "upcoming",
  "ongoing",
  "always_available",
]);

export const LONG_RUNNING_DAYS = 7;
export const ENDING_SOON_DAYS = 7;

const CONTENT_KIND_RANK = Object.freeze({
  dated_event: 0,
  long_running_event: 1,
  recurring_offer: 2,
  permanent_offer: 3,
  undated: 4,
});

const BUCKET_RANK = Object.freeze({
  today: 0,
  this_weekend: 1,
  ending_soon: 2,
  upcoming: 3,
  ongoing: 4,
  always_available: 5,
});

const DATE_FORMATTERS = new Map();

function dateFormatterForCity(city) {
  const timezone = String(city?.timezone || "").trim();
  if (!timezone) return null;
  if (!DATE_FORMATTERS.has(timezone)) {
    DATE_FORMATTERS.set(timezone, new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }));
  }
  return DATE_FORMATTERS.get(timezone);
}

function normalizeConfidence(value) {
  return String(value ?? "").trim().toLocaleLowerCase("en");
}

export function confidenceIsReliable(value) {
  const normalized = normalizeConfidence(value);
  return Boolean(normalized) && !UNRELIABLE_CONFIDENCE.has(normalized);
}

function confidenceIsExplicitlyUnreliable(value) {
  const normalized = normalizeConfidence(value);
  return Boolean(normalized) && UNRELIABLE_CONFIDENCE.has(normalized);
}

export function startIsReliable(event) {
  return confidenceIsReliable(event?.schedule?.start_confidence);
}

export function endIsReliable(event) {
  return Boolean(event?.schedule?.end) && confidenceIsReliable(event?.schedule?.end_confidence);
}

function startIsUsable(event) {
  return !confidenceIsExplicitlyUnreliable(event?.schedule?.start_confidence);
}

function endIsUsable(event) {
  return Boolean(event?.schedule?.end) && !confidenceIsExplicitlyUnreliable(event?.schedule?.end_confidence);
}

export function dateKeyForDate(value, city) {
  const date = value instanceof Date ? value : new Date(value);
  const formatter = dateFormatterForCity(city);
  if (!formatter || Number.isNaN(date.getTime())) return null;
  const parts = formatter.formatToParts(date);
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

export function weekendBounds(todayKey) {
  const weekday = new Date(`${todayKey}T12:00:00Z`).getUTCDay();
  const daysToFriday = weekday === 5 ? 0 : weekday === 6 ? -1 : weekday === 0 ? -2 : 5 - weekday;
  const friday = addDays(todayKey, daysToFriday);
  return { start: friday, end: addDays(friday, 2) };
}

function scheduleWindows(event) {
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

function overallRange(event, city) {
  const ranges = eventDateRanges(event, city);
  if (!ranges.length) return null;
  return {
    start: ranges.reduce((value, range) => value < range.start ? value : range.start, ranges[0].start),
    end: ranges.reduce((value, range) => value > range.end ? value : range.end, ranges[0].end),
  };
}

function normalizedEventText(event) {
  return [
    event?.title,
    event?.description,
    event?.event_type,
    event?.schedule?.display_text,
    ...(event?.tags || []),
  ].filter(Boolean).join(" ")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
}

function hasRecurringSignal(text) {
  if (/\b(?:cada semana|semanal|cada mes|mensual|todos los dias|lunes a viernes|lunes a sabado|martes a domingo|miercoles a domingo|fines de semana)\b/.test(text)) return true;
  return /\b(?:cada|todos los) (?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b/.test(text);
}

function hasPermanentSignal(text) {
  return /\b(?:actividad permanente|oferta permanente|exposicion permanente|visita permanente|todo el ano|sin fecha de termino|horario flexible|a convenir)\b/.test(text);
}

function dayNumber(key) {
  return Date.parse(`${key}T12:00:00Z`) / 86400000;
}

export function classifyContentKind(event, city) {
  const explicit = String(event?.content_kind || "").trim();
  if (CONTENT_KINDS.includes(explicit)) return explicit;

  const range = overallRange(event, city);
  if (range) {
    return dayNumber(range.end) - dayNumber(range.start) > LONG_RUNNING_DAYS
      ? "long_running_event"
      : "dated_event";
  }

  const eventType = String(event?.event_type || "").trim().toLocaleLowerCase("en");
  const text = normalizedEventText(event);
  if (["recurring_offer", "recurring"].includes(eventType) || hasRecurringSignal(text)) return "recurring_offer";
  if (["permanent_offer", "flexible_offer"].includes(eventType) || hasPermanentSignal(text)) return "permanent_offer";
  return "undated";
}

export function isExhibitionLike(event) {
  const values = [
    event?.primary_category?.id,
    event?.primary_category?.label,
    ...(event?.categories || []).flatMap((category) => [category?.id, category?.label]),
  ].filter(Boolean).join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
  return /exposicion|muestra|museo|artes[- ]visuales/.test(values);
}

function firstRelevantRange(event, city, today) {
  const ranges = eventDateRanges(event, city);
  const active = ranges.find((range) => range.start <= today && range.end >= today);
  if (active) return { range: active, active: true, ranges };
  const upcoming = ranges.find((range) => range.end >= today);
  return { range: upcoming || null, active: false, ranges };
}

function temporalBucketForState({ event, kind, relevant, today, scheduleEnd }) {
  if (["recurring_offer", "permanent_offer", "undated"].includes(kind)) return "always_available";
  if (!relevant.range) return null;

  const usableStart = startIsUsable(event);
  const usableEnd = endIsUsable(event);
  if (relevant.active) {
    if (usableStart && (relevant.range.start === today || kind === "dated_event")) return "today";
    const daysUntilEnd = scheduleEnd ? dayNumber(scheduleEnd) - dayNumber(today) : null;
    if (usableEnd && daysUntilEnd !== null && daysUntilEnd >= 0 && daysUntilEnd <= ENDING_SOON_DAYS) return "ending_soon";
    return "ongoing";
  }

  if (!usableStart) return "always_available";
  const weekend = weekendBounds(today);
  if (relevant.range.start <= weekend.end && relevant.range.end >= weekend.start) return "this_weekend";
  return "upcoming";
}

export function classifyTemporalEvent(event, city, now = new Date()) {
  const today = dateKeyForDate(now, city);
  if (!today) return null;
  const kind = classifyContentKind(event, city);
  const relevant = firstRelevantRange(event, city, today);
  const scheduleEnd = dateKeyForValue(event?.schedule?.end, city) || relevant.range?.end || null;
  const bucket = temporalBucketForState({ event, kind, relevant, today, scheduleEnd });
  if (!relevant.range) {
    return {
      today,
      range: null,
      active: false,
      ended: kind === "undated" ? false : true,
      startReliable: startIsReliable(event),
      endReliable: endIsReliable(event),
      exhibition: isExhibitionLike(event),
      scheduleEnd: null,
      daysUntilStart: null,
      daysUntilEnd: null,
      contentKind: kind,
      bucket,
    };
  }
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
    contentKind: kind,
    bucket,
  };
}

export function temporalBadge(event, city, now = new Date()) {
  const state = classifyTemporalEvent(event, city, now);
  if (!state || state.ended || !state.range) return null;
  if (state.startReliable && state.range.start === state.today) return "Hoy";
  if (state.endReliable && state.scheduleEnd === state.today) return "Último día";
  if (state.endReliable && state.active && state.daysUntilEnd > 0 && state.daysUntilEnd <= 3) return "Últimos 3 días";
  if (state.endReliable && state.active && state.daysUntilEnd > 3 && state.daysUntilEnd <= 7) return "Última semana";
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

function spanDays(event, city) {
  const range = overallRange(event, city);
  return range ? dayNumber(range.end) - dayNumber(range.start) : Number.POSITIVE_INFINITY;
}

export function compareTemporalPriority(a, b, city, now = new Date()) {
  const left = classifyTemporalEvent(a, city, now);
  const right = classifyTemporalEvent(b, city, now);
  const bucketDiff = (BUCKET_RANK[left?.bucket] ?? 99) - (BUCKET_RANK[right?.bucket] ?? 99);
  if (bucketDiff) return bucketDiff;
  const kindDiff = (CONTENT_KIND_RANK[left?.contentKind] ?? 99) - (CONTENT_KIND_RANK[right?.contentKind] ?? 99);
  if (kindDiff) return kindDiff;
  const spanDiff = spanDays(a, city) - spanDays(b, city);
  if (Number.isFinite(spanDiff) && spanDiff) return spanDiff;
  if (left?.bucket === "ending_soon") {
    const leftEnd = left?.scheduleEnd || "9999-12-31";
    const rightEnd = right?.scheduleEnd || "9999-12-31";
    const endDiff = leftEnd.localeCompare(rightEnd);
    if (endDiff) return endDiff;
  }
  const timeDiff = eventTimeSortValue(a, city) - eventTimeSortValue(b, city);
  if (Number.isFinite(timeDiff) && timeDiff) return timeDiff;
  return byTitle(a, b, city);
}

export function organizeTemporalPriority(events, city, now = new Date()) {
  const blocks = {
    today: [],
    thisWeekend: [],
    endingSoon: [],
    upcoming: [],
    ongoing: [],
    alwaysAvailable: [],
  };
  const keyByBucket = {
    today: "today",
    this_weekend: "thisWeekend",
    ending_soon: "endingSoon",
    upcoming: "upcoming",
    ongoing: "ongoing",
    always_available: "alwaysAvailable",
  };
  for (const event of events || []) {
    const state = classifyTemporalEvent(event, city, now);
    const key = keyByBucket[state?.bucket];
    if (key) blocks[key].push(event);
  }
  for (const block of Object.values(blocks)) block.sort((a, b) => compareTemporalPriority(a, b, city, now));
  return blocks;
}

export function normalizeTemporalMetadata(dataset, city, now = new Date()) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    const state = classifyTemporalEvent(event, city, now);
    const contentKind = state?.contentKind || classifyContentKind(event, city);
    const temporalBucket = state?.bucket || "always_available";
    if (event?.content_kind === contentKind && event?.temporal_bucket === temporalBucket) return event;
    changed = true;
    return { ...event, content_kind: contentKind, temporal_bucket: temporalBucket };
  });
  return changed ? { ...dataset, events } : dataset;
}

export function shouldSuppressForTemporalFilter(event, when) {
  if (START_BOUNDARY_FILTERS.has(when)) {
    return confidenceIsExplicitlyUnreliable(event?.schedule?.start_confidence);
  }
  if (when === "terminan-pronto") {
    return Boolean(event?.schedule?.end) && confidenceIsExplicitlyUnreliable(event?.schedule?.end_confidence);
  }
  return false;
}
