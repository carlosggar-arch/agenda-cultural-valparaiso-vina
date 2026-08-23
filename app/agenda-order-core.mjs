import {
  CONTENT_KINDS,
  TEMPORAL_BUCKETS,
  classifyTemporalEvent,
  eventDateRanges,
} from "./temporal-priority-core.mjs?v=20260821-temporal4";

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
}

function finiteWeight(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function eventAreaId(event, city, areaWeights) {
  const place = fold([event?.location?.city, event?.location?.commune].filter(Boolean).join(" "));
  if (!place) return null;

  const rankedAreas = (city?.areas || [])
    .map((area, index) => ({
      area,
      index,
      weight: finiteWeight(areaWeights?.[area?.id], Number.POSITIVE_INFINITY),
    }))
    .filter(({ area }) => area?.id && area.id !== "todos")
    .sort((left, right) => left.weight - right.weight || left.index - right.index);

  for (const { area } of rankedAreas) {
    const matches = Array.isArray(area?.match) ? area.match : [];
    if (matches.some((candidate) => {
      const token = fold(candidate);
      return token && place.includes(token);
    })) return area.id;
  }
  return null;
}

function rankIn(values, value) {
  const index = values.indexOf(value);
  return index === -1 ? 99 : index;
}

function dayNumber(key) {
  return Date.parse(`${key}T12:00:00Z`) / 86400000;
}

function eventSpanDays(event, city) {
  const ranges = eventDateRanges(event, city);
  if (!ranges.length) return Number.POSITIVE_INFINITY;
  const start = ranges.reduce((value, range) => value < range.start ? value : range.start, ranges[0].start);
  const end = ranges.reduce((value, range) => value > range.end ? value : range.end, ranges[0].end);
  return dayNumber(end) - dayNumber(start);
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

function compareTitle(a, b, city) {
  return String(a?.title || "").localeCompare(String(b?.title || ""), city?.locale || "es");
}

/**
 * Optional per-city presentation rank used only after the shared temporal
 * semantics are tied. Categories are deliberately neutral here: selecting
 * "Todas" must not make one cultural category intrinsically more important
 * than another. A city may only use local area preferences as a final tie-break.
 */
export function agendaPresentationRank(event, city) {
  const policy = city?.presentation_order;
  if (!policy || typeof policy !== "object") return 0;

  const areaWeights = policy.area_weights || {};
  const defaultAreaRank = finiteWeight(policy.default_area_weight, 0);
  const areaId = eventAreaId(event, city, areaWeights);
  return areaId
    ? finiteWeight(areaWeights[areaId], defaultAreaRank)
    : defaultAreaRank;
}

/**
 * Shared multi-city semantic order, excluding local presentation and title.
 *
 * Global order:
 *   temporal bucket -> content kind -> shorter span -> nearest ending date
 *   (for ending-soon) -> start date/time.
 */
export function compareAgendaSemanticPriority(a, b, city, now = new Date()) {
  const left = classifyTemporalEvent(a, city, now);
  const right = classifyTemporalEvent(b, city, now);

  const bucketDiff = rankIn(TEMPORAL_BUCKETS, left?.bucket) - rankIn(TEMPORAL_BUCKETS, right?.bucket);
  if (bucketDiff) return bucketDiff;

  const kindDiff = rankIn(CONTENT_KINDS, left?.contentKind) - rankIn(CONTENT_KINDS, right?.contentKind);
  if (kindDiff) return kindDiff;

  const spanDiff = eventSpanDays(a, city) - eventSpanDays(b, city);
  if (Number.isFinite(spanDiff) && spanDiff) return spanDiff;

  if (left?.bucket === "ending_soon") {
    const leftEnd = left?.scheduleEnd || "9999-12-31";
    const rightEnd = right?.scheduleEnd || "9999-12-31";
    const endDiff = leftEnd.localeCompare(rightEnd);
    if (endDiff) return endDiff;
  }

  const timeDiff = eventTimeSortValue(a, city) - eventTimeSortValue(b, city);
  if (Number.isFinite(timeDiff) && timeDiff) return timeDiff;
  return 0;
}

/**
 * Single authority for visible agenda ordering in every city.
 *
 * Time and event semantics always come first. City-specific presentation is
 * only an optional tie-break, followed by the localized title. This prevents
 * an area or category preference from outranking an event that is more urgent.
 */
export function compareAgendaOrder(a, b, city, now = new Date()) {
  const semanticDiff = compareAgendaSemanticPriority(a, b, city, now);
  if (semanticDiff) return semanticDiff;

  const presentationDiff = agendaPresentationRank(a, city) - agendaPresentationRank(b, city);
  if (presentationDiff) return presentationDiff;

  return compareTitle(a, b, city);
}
