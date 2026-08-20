import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const fallback = await readFile(new URL("../app/card-image-fallback.js", import.meta.url), "utf8");
const corrections = await readFile(new URL("../app/event-data-corrections.js", import.meta.url), "utf8");
const app = await readFile(new URL("../app/app.js", import.meta.url), "utf8");
const release = await readFile(new URL("../app/release-version.js", import.meta.url), "utf8");

test("runtime-only events are indexed from the shared final normalized snapshot", () => {
  assert.match(fallback, /getAgendaRuntimeSnapshot/);
  assert.match(fallback, /normalizedEvents = snapshot\.events/);
  assert.match(fallback, /eventIndex = new Map\(snapshot\.events\.map/);
  assert.match(fallback, /document\.querySelectorAll\('\[data-agenda\] \.event-card\[data-event-id\]'\)\.forEach\(upgradeRuntimeCard\)/);
  assert.doesNotMatch(fallback, /loadAgendaDataset/);
  assert.doesNotMatch(fallback, /new MutationObserver\s*\(/);
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

test("Valpo presentation modules use the intended cache tokens", () => {
  assert.match(app, /card-experience\.js\?v=20260819-runtime1/);
  assert.match(app, /card-image-fallback\.js\?v=20260819-runtime1/);
  assert.match(app, /public-presentation-guard\.js\?v=20260820-text1/);
  assert.match(app, /exhibition-hours\.js\?v=20260820-hours5/);
  assert.match(app, /schedule-display\.js\?v=20260819-runtime1/);
  assert.doesNotMatch(app, /card-title-consistency\.js\?/);
});

test("image quality guard is retried independently from optional modules", () => {
  assert.match(app, /const IMAGE_QUALITY_GUARD = "\.\/image-quality-guard\.js\?v=20260820-images3"/);
  assert.match(app, /async function loadImageQualityGuard\(\)/);
  assert.match(app, /const delays = \[0, 250, 1000\]/);
  assert.match(app, /await import\(IMAGE_QUALITY_GUARD\)/);
  assert.match(app, /void loadImageQualityGuard\(\)/);
  assert.doesNotMatch(app, /OPTIONAL_MODULES\.push\([\s\S]*image-quality-guard\.js/);
});

test("PWA release changes so Cloudflare and GitHub replace stale presentation caches", () => {
  assert.match(release, /const RELEASE = 161;/);
});
