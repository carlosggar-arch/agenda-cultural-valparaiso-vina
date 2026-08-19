import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function read(path) {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

const combined = read("./combined-filters.js");
const core = read("./app-core.js");
const safety = read("./combined-filters-safety.js");
const browserTest = read("./scripts/test_date_filter_browser.py");
const pwa = read("./pwa.js");
const worker = read("./service-worker.js");
const release = read("./release-version.js");

// Renderer and filters must consume the same normalized dataset.
assert.match(combined, /^import \{ loadAgendaDataset \} from "\.\/data-pipeline\.js/m);
assert.match(combined, /const result = await loadAgendaDataset\(CITY_CONFIG\[cityId\]\)/);
assert.doesNotMatch(
  combined,
  /fetch\s*\(\s*CITY_CONFIG\[cityId\]\.dataset/,
  "combined filters must never reload the raw city dataset independently",
);

// Multi-session events are filtered by normalized occurrences before any fallback range.
assert.match(combined, /const occurrences = event\?\.schedule\?\.occurrences;/);
assert.match(combined, /if \(Array\.isArray\(occurrences\) && occurrences\.length\)/);
assert.match(combined, /return occurrences\.map\(\(occurrence\) => \(\{/);
assert.match(combined, /const ranges = eventDateRanges\(event\);/);

// Both the base sections and combined filter define weekend as Friday through Sunday.
for (const source of [core, combined]) {
  assert.match(source, /const daysToFriday = weekday === 5 \? 0 : weekday === 6 \? -1 : weekday === 0 \? -2 : 5 - weekday;/);
  assert.match(source, /const friday = addDays\(todayKey, daysToFriday\);/);
  assert.match(source, /return \{ start: friday, end: addDays\(friday, 2\) \};/);
  assert.doesNotMatch(source, /daysToSaturday/);
}

// The fail-open layer may restore cards only while the live controls are neutral.
assert.match(safety, /pressedFilterValue\("\[data-combined-when\]"\) !== "todos"/);
assert.match(safety, /pressedFilterValue\("\[data-combined-area\]"\) !== "todos"/);
assert.match(safety, /if \(!currentFilterStateIsNeutral\(\)\) return;/);

// Keep the real-browser regression for both affected dates and grouped cinema sessions.
for (const token of ["2026-08-19", "2026-08-25", "STALE_EVENT_ID", "GROUPED_CINEMA_ID"]) {
  assert.match(browserTest, new RegExp(token.replaceAll("-", "\\-")));
}

// Releases must actively check for a fresh service worker; the worker replaces stale
// shell/data caches immediately, and already-controlled tabs reload once on takeover.
assert.match(pwa, /registration\.update\(\)\.catch\(\(\) => \{\}\)/);
assert.match(worker, /await self\.skipWaiting\(\)/);
assert.match(worker, /await self\.clients\.claim\(\)/);
assert.match(worker, /fetch\(request, \{ cache: "no-store" \}\)/);
assert.match(release, /navigator\.serviceWorker\.addEventListener\("controllerchange"/);
assert.match(release, /window\.location\.reload\(\)/);

console.log("DATE_FILTER_ARCHITECTURE_OK");
