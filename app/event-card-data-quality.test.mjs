import assert from "node:assert/strict";
import test from "node:test";

import {
  browserFriendlySourceUrl,
  currentVisitHours,
  openingHoursForWeekday,
  publicEventSourceUrl,
} from "./event-card-data-quality.mjs";
import { eventForCityPresentation } from "./city-presentation-adapter.mjs";
import { enrichCitySourceEvidence } from "./city-source-evidence-adapter.mjs";
import { normalizeAgendaSourceEvidence } from "./source-evidence-normalizer.mjs";

function prepareGijonSource(event) {
  const enriched = enrichCitySourceEvidence(event, "gijon");
  const canonical = normalizeAgendaSourceEvidence({ events: [enriched] }).events[0];
  return eventForCityPresentation(canonical, "gijon");
}

test("generic source formatter preserves valid public URLs", () => {
  const source = "https://example.org/event?id=728&tipo=XHTML";
  assert.equal(browserFriendlySourceUrl(source), source);
});


test("verified direct source is preserved by the canonical source boundary", () => {
  const event = {
    source_id: "gijon_opendata_events",
    links: {
      official: "https://drupal.gijon.es/es/ficha-rica",
      source: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
    },
    public_status: { external_link_quality: "direct_official" },
  };
  const adapted = prepareGijonSource(event);
  assert.equal(publicEventSourceUrl(adapted), "https://drupal.gijon.es/es/ficha-rica");
});


test("Gijon Open Data fallback is canonicalized before the shared renderer sees it", () => {
  const event = {
    source_id: "gijon_opendata_events",
    links: {
      official: "https://www.gijon.es/evento-que-no-renderiza",
      source: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
      municipal_page: "https://www.gijon.es/evento-que-no-renderiza",
    },
    public_status: { external_link_quality: "opendata_fallback" },
  };
  const adapted = prepareGijonSource(event);
  assert.equal(
    publicEventSourceUrl(adapted),
    "https://opendata.gijon.es/descargar.php?id=728&tipo=PDF",
  );
});


test("weekly opening hours resolve the visible date only", () => {
  const hours = (
    "Lunes a viernes: 9:00 a 21:00. "
    + "Sábados: 11:00 a 14:00 y 16:00 a 21:00. "
    + "Domingos y festivos: 11:00 a 14:00."
  );
  assert.equal(openingHoursForWeekday(hours, "viernes"), "09:00–21:00");
  assert.equal(openingHoursForWeekday(hours, "sábado"), "11:00–14:00 y 16:00–21:00");
  assert.equal(openingHoursForWeekday(hours, "domingo"), "11:00–14:00");
});


test("decimal-dot clock notation is not split as sentence punctuation", () => {
  const hours = "Martes a viernes: 9.30 a 14.00 y de 17.00 a 19.30 horas. Sábados: 10.00 a 14.00.";
  assert.equal(openingHoursForWeekday(hours, "miércoles"), "09:30–14:00 y 17:00–19:30");
  assert.equal(openingHoursForWeekday(hours, "sábado"), "10:00–14:00");
});


test("visit hours are shown only while the dated exhibition is active", () => {
  const event = {
    schedule: {
      start: "2026-07-29",
      end: "2026-08-30",
      opening_hours: {
        display_text: "Martes a viernes: 09:30–14:00 y 17:00–19:30. Sábados y domingos: 10:00–14:00 y 17:00–19:30.",
      },
    },
  };
  assert.equal(currentVisitHours(event, { date: "2026-08-22", weekday: "sábado" }), "10:00–14:00 y 17:00–19:30");
  assert.equal(currentVisitHours(event, { date: "2026-08-31", weekday: "lunes" }), null);
});
