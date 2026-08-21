import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { visibleReferenceDateKey } from "./filter-reference-date.mjs";
import { dateSpecificHours } from "./gijon-venue-hours.js";

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
const scheduleDisplay = read("./schedule-display.js");
const exhibitionHours = read("./exhibition-hours.js");

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

// Venue hours must follow the date visible in the active filter rather than the
// machine's current day. A Saturday in August at Jardín Botánico resolves to the
// August hours only, never to the full seasonal schedule.
const fakeRoot = {
  querySelector(selector) {
    if (selector.includes("[data-combined-when]")) {
      return { dataset: { filterValue: "manana" } };
    }
    return null;
  },
};
assert.equal(
  visibleReferenceDateKey({
    root: fakeRoot,
    timezone: "Europe/Madrid",
    now: new Date("2026-08-21T10:00:00Z"),
  }),
  "2026-08-22",
);
const botanicoSeasonal = "Ene, feb, oct–dic · 10:00–18:00 · marzo 10:00–19:00 · abril y septiembre 10:00–20:00 · mayo–agosto 10:00–21:00. Habitualmente mar–dom; lunes también abre en julio y agosto.";
assert.equal(dateSpecificHours(botanicoSeasonal, "2026-08-22"), "10:00–21:00");
assert.equal(dateSpecificHours(botanicoSeasonal, "2026-08-17"), "10:00–21:00");
assert.equal(dateSpecificHours(botanicoSeasonal, "2026-10-05"), "Cerrado");

// Schedule-display owns event timing; venue opening hours are rendered as a
// separate fact, including grouped exhibitions in Gijón.
assert.match(scheduleDisplay, /scheduleWithoutVisitHours/);
assert.match(scheduleDisplay, /visibleReferenceDateKey/);
assert.match(exhibitionHours, /gijonVenueHoursForDate/);
assert.match(exhibitionHours, /Horario del recinto:/);

// The fail-open layer may restore cards only while the live controls are neutral.
assert.match(safety, /pressedFilterValue\("\[data-combined-when\]"\) !== "todos"/);
assert.match(safety, /pressedFilterValue\("\[data-combined-area\]"\) !== "todos"/);
assert.match(safety, /if \(!currentFilterStateIsNeutral\(\)\) return;/);

// Keep the real-browser regression data-driven: it must derive usable dates from
// the checked-in dataset, prefer recurring cinema when available, and avoid
// fossilised calendar dates that become invalid as the public programme advances.
for (const token of [
  "selected_test_dates",
  "recurring_cinema_candidates",
  "publication_date",
  "STALE_EVENT_ID",
  "GROUPED_CINEMA_ID",
  "for selected in selected_dates",
]) {
  assert.match(browserTest, new RegExp(token));
}
assert.doesNotMatch(browserTest, /for selected in \(\"2026-08-20\", \"2026-08-25\"\)/);

// Releases must actively check for a fresh service worker. The worker can replace
// stale shell/data caches immediately, but taking control must not force a visible
// second page load; the refreshed shell is picked up on the next normal navigation.
assert.match(pwa, /registration\.update\(\)\.catch\(\(\) => \{\}\)/);
assert.match(worker, /await self\.skipWaiting\(\)/);
assert.match(worker, /await self\.clients\.claim\(\)/);
assert.match(worker, /fetch\(request, \{ cache: "no-store" \}\)/);
assert.doesNotMatch(release, /navigator\.serviceWorker\.addEventListener\("controllerchange"/);
assert.doesNotMatch(release, /window\.location\.reload\(\)/);

console.log("DATE_FILTER_ARCHITECTURE_OK");