import {
  areProbableDuplicateEvents,
  mergeDuplicateEvents,
  titleSimilarity,
  titlesLikelySame,
  venuesLikelySame,
  foldEventIdentity,
} from "./event-identity-core.mjs";
import {
  sameLocalOccurrenceDate,
  sameLocalOccurrenceStart,
} from "./occurrence-identity-core.mjs";
import { normalizeAgendaCategories } from "./category-normalizer.js";

export function deduplicateCrossSourceEvents(events) {
  if (!Array.isArray(events) || events.length < 2) return events;
  const output = [];
  for (const event of events) {
    const index = output.findIndex((candidate) => areProbableDuplicateEvents(candidate, event));
    if (index === -1) output.push(event);
    else output[index] = mergeDuplicateEvents(output[index], event);
  }
  return output;
}

function recalculateCounts(events, original = {}) {
  return {
    ...original,
    total: events.length,
    events: events.filter((event) => !["program", "flexible_offer", "course"].includes(event?.event_type)).length,
    courses: events.filter((event) => event?.event_type === "course").length,
    flexible_offers: events.filter((event) => event?.event_type === "flexible_offer").length,
    programs: events.filter((event) => event?.event_type === "program").length,
  };
}

export function deduplicateCrossSourceDataset(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const events = deduplicateCrossSourceEvents(dataset.events);
  const changed = events.length !== dataset.events.length || events.some((event, index) => event !== dataset.events[index]);
  if (!changed) return dataset;

  // A merge can select a different primary source and therefore reintroduce a
  // weak source category (typically the fallback "otros"). Re-run the shared
  // category authority after reconciliation so the merged public record is
  // classified from all of its final evidence, not from merge order.
  return normalizeAgendaCategories({
    ...dataset,
    events,
    counts: recalculateCounts(events, dataset.counts),
  });
}

// Compatibility exports for existing callers/tests. Ownership now lives in the
// identity cores; the orchestrator must not redeclare semantic or occurrence rules.
export {
  areProbableDuplicateEvents,
  mergeDuplicateEvents,
  titleSimilarity,
  titlesLikelySame,
  venuesLikelySame,
  foldEventIdentity as fold,
  sameLocalOccurrenceDate as sameLocalDate,
  sameLocalOccurrenceStart as sameLocalStart,
};
