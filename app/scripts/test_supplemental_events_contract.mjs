import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const read = (relative) => fs.readFileSync(path.join(app, relative), "utf8");

const cities = JSON.parse(read("cities.json"));
const valparaiso = cities.cities.find((city) => city.id === "valparaiso");
assert.ok(valparaiso, "Valparaíso must remain registered");
assert.equal(valparaiso.supplemental_dataset, "./data/valparaiso/supplemental-events.json");

const supplemental = JSON.parse(read("data/valparaiso/supplemental-events.json"));
assert.ok(Array.isArray(supplemental.events));
assert.equal(supplemental.events.length, 1);
const event = supplemental.events[0];
assert.equal(event.title, "Presentación libro // “Decadencia”");
assert.equal(event.primary_category?.id, "otros");
assert.equal(event.primary_category?.label, "Otros panoramas");
assert.equal(event.schedule?.start, "2026-08-27T18:00:00-04:00");
assert.equal(event.schedule?.end, "2026-08-27T20:00:00-04:00");
assert.equal(event.location?.venue, "Palacio Rioja");
assert.equal(event.location?.city, "Viña del Mar");
assert.equal(event.public_status?.source_official, true);
assert.match(event.links?.official || "", /visitavina\.munivina\.cl\/actividad\/presentacion-libro-decadencia/);

const appJs = read("app.js");
const supplementBridge = read("supplemental-events-fetch.js");
const release = read("release-version.js");
assert.doesNotMatch(
  appJs,
  /supplemental-events-fetch\.js/,
  "supplemental dataset remains preserved, but its fetch interceptor must stay out of critical startup until production stability is restored",
);
assert.match(supplementBridge, /supplemental_dataset/);
assert.match(supplementBridge, /mergeEvents/);
assert.doesNotMatch(supplementBridge, /Decadencia|Palacio Rioja/);
const releaseMatch = release.match(/const RELEASE = (\d+);/);
assert.ok(releaseMatch && Number(releaseMatch[1]) >= 126, "PWA release must include the emergency startup unfreeze");

console.log("Supplemental event preserved but startup interceptor disabled: OK");
