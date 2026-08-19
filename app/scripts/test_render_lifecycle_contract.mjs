import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const root = path.resolve(app, "..");
const readApp = (name) => fs.readFileSync(path.join(app, name), "utf8");
const readRoot = (name) => fs.readFileSync(path.join(root, name), "utf8");

const appJs = readApp("app.js");
const pwa = readApp("pwa.js");
const pipeline = readApp("data-pipeline.js");
const runtimeState = readApp("agenda-runtime-state.mjs");
const lifecycle = readApp("render-lifecycle.js");
const cardExperience = readApp("card-experience.js");
const imageFallback = readApp("card-image-fallback.js");
const presentationGuard = readApp("public-presentation-guard.js");
const scheduleDisplay = readApp("schedule-display.js");
const exhibitionHours = readApp("exhibition-hours.js");
const worker = readApp("service-worker.js");
const release = readApp("release-version.js");
const smoke = readRoot("app/scripts/production_pwa_smoke.py");

assert.match(pipeline, /publishAgendaRuntimeSnapshot/);
assert.match(runtimeState, /vivamos:agenda-data-ready/);
assert.match(appJs, /render-lifecycle\.js/);
assert.match(appJs, /card-experience\.js/);
assert.match(appJs, /card-image-fallback\.js/);
assert.match(appJs, /public-presentation-guard\.js/);
assert.match(appJs, /exhibition-hours\.js/);

for (const marker of [
  '"./card-experience.js"',
  '"./card-image-fallback.js"',
  '"./public-presentation-guard.js"',
  '"./schedule-display.js',
  '"./exhibition-hours.js',
]) {
  assert.doesNotMatch(pwa, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
}

for (const [name, source] of [
  ["card-experience", cardExperience],
  ["card-image-fallback", imageFallback],
  ["public-presentation-guard", presentationGuard],
  ["schedule-display", scheduleDisplay],
  ["exhibition-hours", exhibitionHours],
]) {
  assert.match(source, /getAgendaRuntimeSnapshot/, `${name} must consume shared normalized state`);
  assert.match(source, /vivamos:agenda-rendered/, `${name} must react to the bounded render lifecycle`);
  assert.doesNotMatch(source, /new MutationObserver\s*\(/, `${name} must not install its own MutationObserver`);
  assert.doesNotMatch(source, /loadAgendaDataset/, `${name} must not rerun the data pipeline`);
}

assert.doesNotMatch(cardExperience, /\bfetch\s*\(/, "card-experience must not fetch raw datasets");
assert.doesNotMatch(presentationGuard, /\bfetch\s*\(/, "presentation guard must not fetch raw datasets");
assert.doesNotMatch(exhibitionHours, /\bfetch\s*\(/, "exhibition hours must not fetch raw datasets");

assert.match(lifecycle, /new MutationObserver/);
assert.match(lifecycle, /observe\(root, \{ childList: true \}\)/);
assert.doesNotMatch(lifecycle, /subtree:\s*true/);
assert.doesNotMatch(lifecycle, /characterData:\s*true/);
assert.match(lifecycle, /vivamos:agenda-rendered/);

assert.match(worker, /agenda-runtime-state\.mjs/);
assert.match(worker, /render-lifecycle\.js/);
assert.match(smoke, /PRODUCTION_CITY_ROUNDTRIP_OK/);
assert.match(smoke, /valparaiso->gijon->valparaiso/);

const releaseMatch = release.match(/const RELEASE = (\d+);/);
assert.ok(releaseMatch);
assert.ok(Number(releaseMatch[1]) >= 144, "runtime lifecycle hardening requires release v144+");

console.log("Render lifecycle + shared normalized runtime hardening contract: OK");
