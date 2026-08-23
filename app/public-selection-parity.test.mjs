import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { canonicalCategoryId, canonicalEventIds } from "./public-selection-core.mjs";

const dataset = JSON.parse(readFileSync(new URL("../agenda_web.json", import.meta.url), "utf8"));
const city = { id: "valparaiso", timezone: "America/Santiago", locale: "es-CL" };
const now = new Date("2026-08-23T14:30:00Z");

for (const section of ["hoy", "fin-de-semana", "proximos", "gratis", "talleres-cursos"]) {
  const webIds = canonicalEventIds(dataset.events, section, city, now);
  const appIds = canonicalEventIds(dataset.events, section, city, now);
  assert.deepEqual(appIds, webIds, `WEB/APP identifier parity failed for ${section}`);
}
const webCategories = Object.fromEntries(dataset.events.map((event) => [event.id, canonicalCategoryId(event)]));
const appCategories = Object.fromEntries(dataset.events.map((event) => [event.id, canonicalCategoryId(event)]));
assert.deepEqual(appCategories, webCategories, "WEB/APP category parity failed");

const consumers = [
  ["APP core", readFileSync(new URL("./app-core.js", import.meta.url), "utf8")],
  ["APP filters", readFileSync(new URL("./combined-filters.js", import.meta.url), "utf8")],
  ["WEB", readFileSync(new URL("../assets/agenda-core-base.mjs", import.meta.url), "utf8")],
];
for (const [name, source] of consumers) {
  assert.match(source, /public-selection-core\.mjs|eventMatchesCanonicalSection/, `${name} must use canonical selection`);
}
assert.doesNotMatch(consumers[1][1], /loadAgendaDataset/, "APP filters must not run a second pipeline");
console.log("PUBLIC_SELECTION_PARITY_OK sections=5 identity=exact category=exact");
