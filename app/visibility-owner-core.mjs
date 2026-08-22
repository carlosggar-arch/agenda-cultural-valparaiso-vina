import { shouldSuppressForTemporalFilter } from "./temporal-priority-core.mjs?v=20260821-temporal4";

/**
 * Pure visibility state for a top-level event card.
 *
 * `hidden` preserves the combined-filter decision. `temporalSuppressed` is a
 * separate visual guard on purpose: the legacy runtime hid unreliable date
 * cards with CSS without changing `.hidden`, so counts and filter summaries
 * remain A-equivalent during C2.
 */
export function directCardVisibilityState(event, matchesFilters, when) {
  return {
    hidden: !matchesFilters,
    temporalSuppressed: Boolean(event && shouldSuppressForTemporalFilter(event, when)),
  };
}

/**
 * Pure visibility state for a grouped exhibition card.
 * Temporal confidence suppression historically applied only to direct cards;
 * grouped rows therefore remain governed exclusively by filter membership in
 * this behavior-preserving refactor.
 */
export function groupedCardVisibilityState(groupIds, matchingIds) {
  const ids = Array.isArray(groupIds) ? groupIds : [];
  const matches = matchingIds instanceof Set ? matchingIds : new Set(matchingIds || []);
  const rowHidden = ids.map((id) => !matches.has(String(id || "")));
  const visibleCount = rowHidden.reduce((count, hidden) => count + (hidden ? 0 : 1), 0);
  return {
    rowHidden,
    visibleCount,
    hidden: visibleCount === 0,
  };
}
