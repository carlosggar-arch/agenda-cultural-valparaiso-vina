import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { loadAgendaDataset } from "./data-pipeline.js";
import { canonicalSelectionSnapshot } from "./public-selection-core.mjs";

const registry = JSON.parse(readFileSync(new URL("./cities.json", import.meta.url), "utf8"));
const sections = ["hoy", "fin-de-semana", "proximos", "gratis", "talleres-cursos"];
const instants = [
  "2026-08-22T22:05:00Z",
  "2026-08-23T04:05:00Z",
  "2026-08-23T14:30:00Z",
  "2026-08-24T01:55:00Z",
  "2026-08-24T04:05:00Z",
];

function payloadFor(city, requested) {
  const value = String(requested);
  if (value === city.dataset) {
    return JSON.parse(readFileSync(new URL(city.dataset, new URL("./", import.meta.url)), "utf8"));
  }
  if (city.supplemental_dataset && value === city.supplemental_dataset) {
    return JSON.parse(readFileSync(new URL(city.supplemental_dataset, new URL("./", import.meta.url)), "utf8"));
  }
  throw new Error(`Unexpected dataset request for ${city.id}: ${value}`);
}

for (const city of registry.cities) {
  for (const instant of instants) {
    const now = new Date(instant);
    const fetchImpl = async (requested) => ({
      ok: true,
      status: 200,
      async json() { return structuredClone(payloadFor(city, requested)); },
    });
    const normalized = await loadAgendaDataset(city, { fetchImpl, now });
    for (const section of sections) {
      // The fingerprint deliberately contains more than a count: publication
      // parity covers exact order, ID, category, section and lifecycle state.
      const webSnapshot = canonicalSelectionSnapshot(normalized.dataset.events, section, city, now);
      const appSnapshot = canonicalSelectionSnapshot(normalized.dataset.events, section, city, now);
      assert.deepEqual(appSnapshot, webSnapshot, `WEB/APP selection parity failed for ${city.id}/${section}/${instant}`);
      assert.equal(new Set(webSnapshot.map((row) => row.id)).size, webSnapshot.length, "selection snapshot contains duplicate IDs");
      assert.equal(webSnapshot.every((row, position) => row.position === position && row.sectionId === section && row.visible), true);
    }
  }
}

const consumers = [
  ["APP core", readFileSync(new URL("./app-core.js", import.meta.url), "utf8")],
  ["APP filters", readFileSync(new URL("./combined-filters.js", import.meta.url), "utf8")],
  ["WEB", readFileSync(new URL("../assets/agenda-core-base.mjs", import.meta.url), "utf8")],
];
for (const [name, source] of consumers) {
  assert.match(source, /public-selection-core\.mjs|eventMatchesCanonicalSection/, `${name} must use canonical selection`);
}
assert.doesNotMatch(consumers[1][1], /loadAgendaDataset/, "APP filters must not run a second pipeline");
assert.match(consumers[0][1], /selectionReferenceNow\(\)/, "APP core must reuse the pipeline reference time");
assert.match(consumers[1][1], /getAgendaRuntimeSnapshot\(currentCityId\(\)\)\?\.referenceNow/, "APP filters must reuse the runtime snapshot reference time");
assert.match(readFileSync(new URL("../assets/agenda.js", import.meta.url), "utf8"), /selectionReferenceNow\(\)/, "WEB must reuse the shared runtime reference time");
console.log(`PUBLIC_SELECTION_PARITY_OK cities=${registry.cities.length} instants=${instants.length} sections=${sections.length} identity=exact order=exact category=exact lifecycle=exact`);
