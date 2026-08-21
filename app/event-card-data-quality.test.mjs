import assert from "node:assert/strict";
import test from "node:test";

import {
  browserFriendlySourceUrl,
  currentVisitHours,
  openingHoursForWeekday,
  publicEventSourceUrl,
} from "./event-card-data-quality.mjs";


test("Open Data XHTML fallback becomes browser-readable PDF", () => {
  const source = "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML";
  assert.equal(
    browserFriendlySourceUrl(source),
    "https://opendata.gijon.es/descargar.php?id=728&tipo=PDF",
  );
});


test("verified direct source is preserved", () => {
  const event = {
    source_id: "gijon_opendata_events",
    links: {
      official: "https://drupal.gijon.es/es/ficha-rica",
      source: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
    },
    public_status: { external_link_quality: "direct_official" },
  };
  assert.equal(publicEventSourceUrl(event), "https://drupal.gijon.es/es/ficha-rica");
});


test("Open Data fallback does not surface an unreliable municipal shell", () => {
  const event = {
    source_id: "gijon_opendata_events",
    links: {
      official: "https://www.gijon.es/evento-que-no-renderiza",
      source: "https://opendata.gijon.es/descargar.php?id=728&tipo=XHTML",
      municipal_page: "https://www.gijon.es/evento-que-no-renderiza",
    },
    public_status: { external_link_quality: "opendata_fallback" },
  };
  assert.equal(
    publicEventSourceUrl(event),
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
        display_text: "Lunes a viernes: 9:00 a 21:00. Sábados: 11:00 a 14:00 y 16:00 a 21:00.",
      },
    },
  };

  assert.equal(
    currentVisitHours(event, {
      now: new Date("2026-08-21T10:00:00Z"),
      timezone: "Europe/Madrid",
    }),
    "09:00–21:00",
  );
  assert.equal(
    currentVisitHours(event, {
      now: new Date("2026-09-02T10:00:00Z"),
      timezone: "Europe/Madrid",
    }),
    null,
  );
});
