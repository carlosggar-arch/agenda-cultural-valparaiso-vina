import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { enrichCitySourceEvidence } from "./city-source-evidence-adapter.mjs";
import { normalizeAgendaSourceEvidence } from "./source-evidence-normalizer.mjs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const pipeline = read("./data-pipeline.js");
const presentationAdapter = read("./city-presentation-adapter.mjs");

const verified = {
  id: "gijon-verified",
  source_id: "gijon_opendata_events",
  source_name: "Open Data Gijón/Xixón",
  source_url: "https://opendata.gijon.es/descargar.php?id=777&tipo=XHTML",
  organizer: "Ayuntamiento de Gijón/Xixón",
  location: { venue: "Centro de Cultura Antiguo Instituto", city: "Gijón" },
  links: {
    source: "https://opendata.gijon.es/descargar.php?id=777&tipo=XHTML",
    official: "https://www.gijon.es/",
    municipal_page: "https://www.gijon.es/exposicion-mientras-tu-dormias",
  },
  public_status: { external_link_quality: "opendata_fallback" },
};

const enrichedVerified = enrichCitySourceEvidence(verified, "gijon");
assert.equal(enrichedVerified.source_url, verified.source_url, "city evidence adapter must not write canonical source fields");
assert.equal(enrichedVerified.source_name, verified.source_name, "city evidence adapter must not rewrite source names");
assert.equal(enrichedVerified.source_evidence.length, 1);
assert.equal(enrichedVerified.source_evidence[0].url, "https://www.gijon.es/exposicion-mientras-tu-dormias");
assert.equal(enrichedVerified.source_evidence[0].presentation_preferred, true);

const normalizedVerified = normalizeAgendaSourceEvidence({ events: [enrichedVerified] }).events[0];
assert.equal(normalizedVerified.source_url, "https://www.gijon.es/exposicion-mientras-tu-dormias");
assert.equal(normalizedVerified.source_name, "Ayuntamiento de Gijón/Xixón");
assert.equal(normalizedVerified.links.official, normalizedVerified.source_url);
assert.equal(normalizedVerified.links.presentation_source, normalizedVerified.source_url);
assert.equal(normalizedVerified.links.source, normalizedVerified.source_url);
assert.ok(
  normalizedVerified.secondary_source_urls.includes("https://opendata.gijon.es/descargar.php?id=777&tipo=XHTML"),
  "replacing the presentation source must preserve the previous evidence as secondary",
);

const fallback = {
  id: "gijon-opendata-fallback",
  source_id: "gijon_opendata_events",
  source_name: "Open Data Gijón/Xixón",
  source_url: "https://opendata.gijon.es/descargar.php?id=790&tipo=XHTML",
  links: {
    source: "https://opendata.gijon.es/descargar.php?id=790&tipo=XHTML",
    official: "https://www.gijon.es/",
  },
  public_status: { external_link_quality: "opendata_fallback" },
};
const normalizedFallback = normalizeAgendaSourceEvidence({
  events: [enrichCitySourceEvidence(fallback, "gijon")],
}).events[0];
assert.equal(normalizedFallback.source_url, "https://opendata.gijon.es/descargar.php?id=790&tipo=PDF");
assert.equal(normalizedFallback.links.official, normalizedFallback.source_url);

assert.doesNotMatch(
  presentationAdapter,
  /presentationLinksForGijon|browserFriendlyGijonUrl|source_url:\s*source|source_name:\s*source|presentation_source/,
  "presentation adapter must be read-only for source evidence",
);
assert.match(pipeline, /city-source-evidence-adapter\.mjs/, "pipeline must ingest city evidence through a dedicated adapter");
assert.ok(
  pipeline.indexOf('"cross-source-deduplication"') < pipeline.indexOf('"city-source-evidence-adapter"'),
  "merged source evidence must exist before city corroborations are added",
);
assert.ok(
  pipeline.indexOf('"city-source-evidence-adapter"') < pipeline.indexOf('"source-evidence-normalizer"'),
  "canonical source chooser must run after all corroborations are present",
);

console.log("SINGLE_SOURCE_EVIDENCE_AUTHORITY_OK");
