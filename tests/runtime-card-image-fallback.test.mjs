import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const cards = await readFile(new URL("../app/card-experience.js", import.meta.url), "utf8");
const imageGuard = await readFile(new URL("../app/image-quality-guard.js", import.meta.url), "utf8");
const corrections = await readFile(new URL("../app/event-data-corrections.js", import.meta.url), "utf8");
const app = await readFile(new URL("../app/app.js", import.meta.url), "utf8");
const release = await readFile(new URL("../app/release-version.js", import.meta.url), "utf8");

test("cards and fallback images use the shared final normalized snapshot", () => {
  assert.match(cards, /getAgendaRuntimeSnapshot/);
  assert.match(cards, /eventIndex = new Map\(snapshot\.events\.map/);
  assert.match(imageGuard, /getAgendaRuntimeSnapshot/);
  assert.match(imageGuard, /eventIndex = new Map\(snapshot\.events/);
  assert.doesNotMatch(cards, /loadAgendaDataset|new MutationObserver\s*\(/);
  assert.doesNotMatch(imageGuard, /loadAgendaDataset|new MutationObserver\s*\(/);
});

test("one common card renderer owns event, venue and category image fallbacks", () => {
  assert.match(cards, /function relevantImageUrl\(event\)/);
  assert.match(cards, /function representativeImageUrl\(event\)/);
  assert.match(cards, /function buildMedia\(event\)/);
  assert.match(imageGuard, /function installCategoryFallback\(card, media\)/);
  assert.match(imageGuard, /image\.dataset\.imageKind = "category-fallback"/);
});

test("retired parallel card image renderers are not loaded", () => {
  assert.doesNotMatch(app, /card-image-fallback\.js|gijon-card-images\.js/);
  assert.match(app, /card-experience\.js\?v=20260821-shared-runtime1/);
  assert.match(app, /image-quality-guard\.js\?v=20260821-shared-runtime1/);
  assert.match(app, /public-presentation-guard\.js\?v=20260821-shared-runtime1/);
  assert.match(app, /exhibition-hours\.js\?v=20260821-gijonhours1/);
  assert.match(app, /exhibition-groups\.js\?v=20260821-single-owner1/);
  assert.match(app, /schedule-display\.js\?v=20260819-runtime1/);
  assert.doesNotMatch(app, /static-exhibition-groups\.js|card-title-consistency\.js\?/);
});

test("image quality guard is part of the same optional common runtime", () => {
  const optionalBlock = app.match(/const OPTIONAL_MODULES = \[([\s\S]*?)\];/)?.[1] || "";
  assert.match(optionalBlock, /card-experience\.js/);
  assert.match(optionalBlock, /image-quality-guard\.js/);
  assert.doesNotMatch(app, /loadImageQualityGuard|IMAGE_QUALITY_GUARD|IS_GIJON/);
});

test("Palacio Rioja Qi Gong and Jacques Tati corrections stay covered", () => {
  for (const id of [
    "agenda_rioja_20260819_qigong",
    "agenda_rioja_20260819_mitio",
    "agenda_rioja_20260826_qigong",
    "agenda_rioja_20260826_playtime",
  ]) assert.match(corrections, new RegExp(id));
});

test("PWA release is new enough to replace stale presentation caches", () => {
  const match = release.match(/const RELEASE = (\d+);/);
  assert.ok(match, "release-version.js must expose a numeric release");
  assert.ok(Number(match[1]) >= 182, "PWA release must include the shared presentation runtime cache boundary");
});
