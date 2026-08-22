import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  directCardVisibilityState,
  groupedCardVisibilityState,
} from "./visibility-owner-core.mjs";

function legacyDirectState(event, matchesFilters, when) {
  const startUnreliable = ["technical_fallback", "derived_fallback", "unreliable"].includes(event?.schedule?.start_confidence);
  const endUnreliable = ["technical_fallback", "derived_fallback", "unreliable"].includes(event?.schedule?.end_confidence);
  const startBoundary = new Set(["hoy", "manana", "fin-de-semana", "7-dias", "personalizado"]);
  return {
    hidden: !matchesFilters,
    temporalSuppressed: startBoundary.has(when)
      ? startUnreliable
      : when === "terminan-pronto" && Boolean(event?.schedule?.end) && endUnreliable,
  };
}

const directCases = [
  [{ schedule: { start_confidence: "explicit" } }, true, "hoy"],
  [{ schedule: { start_confidence: "technical_fallback" } }, true, "hoy"],
  [{ schedule: { start_confidence: "technical_fallback" } }, false, "hoy"],
  [{ schedule: { start_confidence: "technical_fallback" } }, true, "todos"],
  [{ schedule: { end: "2026-08-23", end_confidence: "technical_fallback" } }, true, "terminan-pronto"],
  [{ schedule: { end: "2026-08-23", end_confidence: "explicit" } }, true, "terminan-pronto"],
];

for (const [event, matches, when] of directCases) {
  assert.deepEqual(
    directCardVisibilityState(event, matches, when),
    legacyDirectState(event, matches, when),
    `C2 direct visibility must remain A-equivalent for ${when}`,
  );
}

function legacyGroupedState(groupIds, matchingIds) {
  const rowHidden = groupIds.map((id) => !matchingIds.has(id));
  const visibleCount = rowHidden.filter((hidden) => !hidden).length;
  return { rowHidden, visibleCount, hidden: visibleCount === 0 };
}

for (const matching of [
  new Set(["a", "b", "c"]),
  new Set(["b"]),
  new Set(),
]) {
  assert.deepEqual(
    groupedCardVisibilityState(["a", "b", "c"], matching),
    legacyGroupedState(["a", "b", "c"], matching),
    "C2 grouped visibility must remain A-equivalent",
  );
}

const combined = readFileSync(new URL("./combined-filters.js", import.meta.url), "utf8");
const temporal = readFileSync(new URL("./temporal-priority.js", import.meta.url), "utf8");
const exhibitionGuard = readFileSync(new URL("./exhibition-presentation-guard.js", import.meta.url), "utf8");
const safety = readFileSync(new URL("./combined-filters-safety.js", import.meta.url), "utf8");

assert.match(combined, /visibility-owner-core\.mjs/, "combined filters must consume canonical visibility decisions");
assert.match(combined, /card\.hidden\s*=/, "combined filters must own top-level card hidden state");
assert.match(combined, /rows\[index\]\.hidden\s*=/, "combined filters must own grouped-row hidden state");
assert.match(combined, /dataset\.temporalSuppressed/, "combined filters must own temporal visual suppression");
assert.match(combined, /data-combined-visibility-styles/, "combined filters must own the temporal suppression CSS");
assert.match(combined, /vivamos:visibility-reconcile-requested/, "combined filters must accept visibility reconciliation requests");

assert.doesNotMatch(temporal, /\.hidden\s*=|temporalSuppressed|display\s*:\s*none/, "temporal presentation must not write event visibility");
assert.doesNotMatch(exhibitionGuard, /\.hidden\s*=/, "exhibition guard must not write card or row visibility");
assert.match(exhibitionGuard, /vivamos:visibility-reconcile-requested/, "exhibition consolidation must delegate visibility reconciliation");
assert.match(safety, /combined-filters\.js remains the[\s\S]*sole owner/, "safety contract must agree with the active visibility owner");

console.log("C2_VISIBILITY_SINGLE_OWNER_A_EQUIVALENCE_OK");
