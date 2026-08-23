import { eventDateRanges } from "./temporal-priority-core.mjs?v=20260821-temporal4";

export const EDITORIAL_PRIORITY_WEIGHTS = Object.freeze({
  official_source: 3,
  corroborated_source: 2,
  complete_information: 1,
  one_day_event: 1,
  explicit_special_event: 2,
});

const SPECIAL_EVENT_TOKENS = new Set([
  "estreno",
  "premiere",
  "inauguracion",
  "apertura",
  "funcion_unica",
  "unique_performance",
  "one_off",
  "evento_unico",
]);

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function absoluteHttpUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function corroboratingSource(event) {
  const links = event?.links || {};
  return absoluteHttpUrl(
    links.presentation_source
      || links.corroborating
      || links.verified_source
      || links.secondary_source,
  );
}

function explicitSpecialEvent(event) {
  const editorial = event?.editorial || {};
  const values = [
    editorial.priority_flag,
    editorial.feature_flag,
    ...(Array.isArray(editorial.priority_flags) ? editorial.priority_flags : []),
    ...(Array.isArray(editorial.flags) ? editorial.flags : []),
    ...(Array.isArray(event?.tags) ? event.tags : []),
  ].map(fold).filter(Boolean);
  return values.some((value) => SPECIAL_EVENT_TOKENS.has(value));
}

function oneDayEvent(event, city) {
  const ranges = eventDateRanges(event, city);
  if (!ranges.length) return false;
  const dates = new Set();
  for (const range of ranges) {
    if (range.start !== range.end) return false;
    dates.add(range.start);
  }
  return dates.size === 1;
}

/**
 * Transparent, city-agnostic editorial tie-break metadata.
 *
 * This score is intentionally small and factual. It is not a cultural quality
 * judgment and must never replace temporal/event semantics. The canonical
 * agenda comparator consumes it only after the temporal semantic key is tied.
 */
export function editorialPriority(event, city) {
  const signals = [];
  let score = 0;

  if (event?.public_status?.source_official === true) {
    score += EDITORIAL_PRIORITY_WEIGHTS.official_source;
    signals.push("official_source");
  }

  if (corroboratingSource(event)) {
    score += EDITORIAL_PRIORITY_WEIGHTS.corroborated_source;
    signals.push("corroborated_source");
  }

  if (String(event?.public_status?.information_completeness || "").toLocaleLowerCase("en") === "complete") {
    score += EDITORIAL_PRIORITY_WEIGHTS.complete_information;
    signals.push("complete_information");
  }

  if (oneDayEvent(event, city)) {
    score += EDITORIAL_PRIORITY_WEIGHTS.one_day_event;
    signals.push("one_day_event");
  }

  if (explicitSpecialEvent(event)) {
    score += EDITORIAL_PRIORITY_WEIGHTS.explicit_special_event;
    signals.push("explicit_special_event");
  }

  return Object.freeze({ score, signals: Object.freeze(signals) });
}

export function compareEditorialPriority(a, b, city) {
  return editorialPriority(b, city).score - editorialPriority(a, city).score;
}
