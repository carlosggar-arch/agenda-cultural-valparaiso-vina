import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const fallback = await readFile(new URL("../app/card-image-fallback.js", import.meta.url), "utf8");
const corrections = await readFile(new URL("../app/event-data-corrections.js", import.meta.url), "utf8");
const app = await readFile(new URL("../app/app.js", import.meta.url), "utf8");

test("runtime-only events are indexed from the final normalized pipeline", () => {
  assert.match(fallback, /import \{ loadAgendaDataset \} from "\.\/data-pipeline\.js\?v=20260819-pipeline1"/);
  assert.match(fallback, /const result = await loadAgendaDataset\(city\)/);
  assert.match(fallback, /eventIndex = new Map\(events\.map/);
  assert.match(fallback, /document\.querySelectorAll\('\[data-agenda\] \.event-card\[data-event-id\]'\)\.forEach\(upgradeRuntimeCard\)/);
});

test("runtime cards always get event, venue, or category artwork", () => {
  assert.match(fallback, /function eventImageChoice\(event\)/);
  assert.match(fallback, /if \(specific\) return \{ url: specific, representative: false \}/);
  assert.match(fallback, /if \(sameVenue\) return \{ url: sameVenue, representative: true \}/);
  assert.match(fallback, /return \{ url: categoryPhoto\(categoryLabel\(event\)\), representative: false, categoryFallback: true \}/);
  assert.match(fallback, /function upgradeRuntimeCard\(card\)/);
});

test("Palacio Rioja Qi Gong and Jacques Tati corrections stay covered", () => {
  for (const id of [
    "agenda_rioja_20260819_qigong",
    "agenda_rioja_20260819_mitio",
    "agenda_rioja_20260826_qigong",
    "agenda_rioja_20260826_playtime",
  ]) assert.match(corrections, new RegExp(id));
});

test("Valpo image modules use the post-repair cache token", () => {
  assert.match(app, /card-experience\.js\?v=20260819-valpoimages2/);
  assert.match(app, /card-image-fallback\.js\?v=20260819-valpoimages2/);
  assert.match(app, /card-title-consistency\.js\?v=20260819-titleguard1/);
});
