import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const cards = await readFile(new URL("../app/card-experience.js", import.meta.url), "utf8");
const imageGuard = await readFile(new URL("../app/image-quality-guard.js", import.meta.url), "utf8");
const groups = await readFile(new URL("../app/exhibition-groups.js", import.meta.url), "utf8");
const detail = await readFile(new URL("../app/event-detail.js", import.meta.url), "utf8");
const resolver = await readFile(new URL("../app/image-resolver-core.mjs", import.meta.url), "utf8");
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

test("one pure resolver owns image selection across cards, groups, detail and guard", () => {
  for (const source of [cards, imageGuard, groups, detail]) {
    assert.match(source, /image-resolver-core\.mjs\?v=/);
  }
  assert.match(resolver, /export function resolveEventImage\(/);
  assert.match(resolver, /export function resolveCardImageAfterFailure\(/);
  assert.match(resolver, /export function categoryFallbackImage\(/);
  assert.match(resolver, /export function generatedEventFallbackImage\(/);
  assert.match(resolver, /export function shouldInstallCategoryFallback\(/);

  assert.doesNotMatch(cards, /function venueImageKey\(|function buildVenueImagePools\(|function looksLikeGenericSchedule\(/);
  assert.doesNotMatch(imageGuard, /GENERIC_PROVIDER_HOSTS|CATEGORY_IMAGES|function isGenericImage\(|function categoryIdForCard\(/);
  assert.doesNotMatch(groups, /const url = String\(event\?\.image\?\.url/);
  assert.doesNotMatch(detail, /presentation\?\.imageRelevant === false \? null : safeHttpUrl\(event\?\.image\?\.url\)/);
});

test("grouped exhibitions resolve owned images under the active app base and fail visibly to fallback", () => {
  assert.match(groups, /resolveEventImage\(event, \{ surface: "group", baseUrl: location\.href \}\)/);
  assert.match(groups, /img\.src = url \|\| FALLBACK_IMAGE/);
  assert.match(groups, /if \(eventId && url\)/);
  assert.match(groups, /img\.dataset\.eventImage = "relevant"/);
  assert.match(groups, /img\.dataset\.eventImageId = eventId/);
  assert.match(groups, /img\.addEventListener\("error", \(\) => \{ img\.src = FALLBACK_IMAGE; \}/);
});

test("generated event fallback keeps explicit runtime presentation markers", () => {
  assert.match(imageGuard, /image\.dataset\.imageKind = "generated-fallback"/);
  assert.match(imageGuard, /image\.dataset\.imageQualityFallback = "true"/);
  assert.match(imageGuard, /media\.dataset\.generatedEventImage = "true"/);
  assert.match(imageGuard, /generatedEventFallbackImage/);
});

test("retired parallel card image renderers are not loaded", () => {
  assert.doesNotMatch(app, /card-image-fallback\.js|gijon-card-images\.js/);
  assert.match(app, /card-experience\.js\?v=20260821-shared-runtime1/);
  assert.match(app, /image-quality-guard\.js\?v=20260821-shared-runtime1/);
  assert.match(app, /public-presentation-guard\.js\?v=20260821-shared-runtime1/);
  assert.match(app, /exhibition-hours\.js\?v=[^"\s]+/);
  assert.match(app, /exhibition-groups\.js\?v=[^"\s]+/);
  assert.match(app, /schedule-display\.js\?v=[^"\s]+/);
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
  assert.ok(Number(match[1]) >= 196, "PWA release must include the single image resolver boundary");
});
