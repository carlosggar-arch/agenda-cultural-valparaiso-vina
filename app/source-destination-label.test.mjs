import assert from "node:assert/strict";
import { enrichCitySourceEvidence } from "./city-source-evidence-adapter.mjs";
import { normalizeAgendaSourceEvidence } from "./source-evidence-normalizer.mjs";

const base = {
  id: "gallery", source_id: "gijon_opendata_events",
  source_name: "Open Data Ayuntamiento de Gijón/Xixón — Agenda de Eventos",
  source_url: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
  public_status: { source_official: true, external_link_quality: "direct_official" },
};
for (const [url, label] of [
  ["https://www.atmgaleria.com/", "atmgaleria.com"],
  ["https://www.beavillamarin.com/", "beavillamarin.com"],
  ["https://drupal.gijon.es/es/exposicion", "Ayuntamiento de Gijón/Xixón"],
]) {
  const input = { ...base, links: { official: url, source: base.source_url } };
  const [event] = normalizeAgendaSourceEvidence({ events: [enrichCitySourceEvidence(input, "gijon")] }).events;
  assert.equal(event.source_name, label);
  assert.equal(event.source_url, url);
  assert.equal(event.links.presentation_source, url);
  assert.ok(event.secondary_source_urls.some((value) => value.includes("opendata.gijon.es")));
}
assert.equal(enrichCitySourceEvidence(base, "valparaiso"), base);
