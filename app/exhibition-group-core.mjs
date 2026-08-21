import { canonicalPublicCategoryId, isPublicCategoryInGroup } from "./public-category-rules.mjs";

export const EXHIBITION_GROUP_MIN = 2;
export const LONG_EXHIBITION_DAYS = 7;

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function publicExhibitionCategoryId(event) {
  const primary = event?.primary_category || null;
  if (isPublicCategoryInGroup(primary, "exhibition")) return "exposiciones";
  for (const category of event?.categories || []) {
    if (isPublicCategoryInGroup(category, "exhibition")) return "exposiciones";
  }
  return canonicalPublicCategoryId(primary) || String(primary?.id || "").trim();
}

export function exhibitionVenueKey(event) {
  if (publicExhibitionCategoryId(event) !== "exposiciones") return null;
  const venue = String(event?.location?.venue || "").trim();
  if (!venue) return null;
  const city = String(event?.location?.city || "").trim();
  return fold(`${venue}|${city}`);
}

export function dateKey(value, timezone) {
  const text = String(value || "").trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone || "UTC",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function exhibitionRange(event, timezone) {
  const schedule = event?.schedule || {};
  const windows = Array.isArray(schedule.occurrences) && schedule.occurrences.length
    ? schedule.occurrences
    : schedule.start
      ? [{ start: schedule.start, end: schedule.end || schedule.start }]
      : [];
  const ranges = windows
    .map((window) => ({
      start: dateKey(window?.start, timezone),
      end: dateKey(window?.end || window?.start, timezone),
    }))
    .filter((range) => range.start && range.end);
  if (!ranges.length) return null;
  return {
    start: ranges.reduce((value, range) => range.start < value ? range.start : value, ranges[0].start),
    end: ranges.reduce((value, range) => range.end > value ? range.end : value, ranges[0].end),
  };
}

export function exhibitionDurationDays(event, { timezone = "UTC" } = {}) {
  const range = exhibitionRange(event, timezone);
  if (!range) return null;
  const start = Date.parse(`${range.start}T12:00:00Z`);
  const end = Date.parse(`${range.end}T12:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return (end - start) / 86400000;
}

export function isLongExhibitionDuration(event, options = {}) {
  const days = exhibitionDurationDays(event, options);
  return Number.isFinite(days) && days > LONG_EXHIBITION_DAYS;
}

export function partitionExhibitionsByDuration(events, options = {}) {
  const regular = [];
  const long = [];
  for (const event of events || []) {
    (isLongExhibitionDuration(event, options) ? long : regular).push(event);
  }
  return { regular, long };
}

export function clusterSimultaneousExhibitions(events, { timezone = "UTC" } = {}) {
  const sortable = events
    .map((event) => ({ event, range: exhibitionRange(event, timezone) }))
    .filter((item) => item.range)
    .sort((a, b) => a.range.start.localeCompare(b.range.start) || a.range.end.localeCompare(b.range.end));

  const clusters = [];
  for (const item of sortable) {
    let placed = false;
    for (const cluster of clusters) {
      if (item.range.start <= cluster.commonEnd && item.range.end >= cluster.commonStart) {
        cluster.events.push(item.event);
        cluster.commonStart = item.range.start > cluster.commonStart ? item.range.start : cluster.commonStart;
        cluster.commonEnd = item.range.end < cluster.commonEnd ? item.range.end : cluster.commonEnd;
        placed = true;
        break;
      }
    }
    if (!placed) {
      clusters.push({
        events: [item.event],
        commonStart: item.range.start,
        commonEnd: item.range.end,
      });
    }
  }
  return clusters;
}

export function groupStandaloneExhibitions(events, { timezone = "UTC", minSize = EXHIBITION_GROUP_MIN } = {}) {
  const byVenue = new Map();
  for (const event of events) {
    const key = exhibitionVenueKey(event);
    if (!key) continue;
    const bucket = byVenue.get(key) || [];
    bucket.push(event);
    byVenue.set(key, bucket);
  }

  const groups = [];
  for (const [venueKey, bucket] of byVenue) {
    for (const cluster of clusterSimultaneousExhibitions(bucket, { timezone })) {
      if (cluster.events.length >= minSize) groups.push({ venueKey, ...cluster });
    }
  }
  return groups;
}
