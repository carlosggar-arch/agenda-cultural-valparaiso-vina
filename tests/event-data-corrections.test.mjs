import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../app/event-data-corrections.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { applyEventDataCorrections } = await import(moduleUrl);

function fixture() {
  return {
    counts: { total: 1, events: 1, courses: 0, flexible_offers: 0, programs: 0 },
    events: [{
      id: "agenda_970a461a24590f90dad68803",
      title: "Danza Segunda Bienal de Danza Moderna y Contemporánea de la Región de Valparaíso",
      event_type: "event",
      source_url: "https://parquecultural.cl/events/segunda-bienal-de-danza-moderna-y-contemporanea-de-la-region-de-valparaiso-2026-08-19/",
      links: { official: "https://parquecultural.cl/events/segunda-bienal-de-danza-moderna-y-contemporanea-de-la-region-de-valparaiso-2026-08-19/" },
      schedule: {
        mode: "dated",
        start: "2026-08-19T19:00:00-04:00",
        end: null,
        timezone: "America/Santiago",
        display_text: "2026-08-19 · 19:00",
        occurrences: [{ start: "2026-08-19T19:00:00-04:00", end: null }],
      },
      tags: [],
    }],
  };
}

const corrected = applyEventDataCorrections(fixture());
assert.equal(corrected.events.length, 18);
assert.equal(corrected.counts.total, 18);
assert.equal(corrected.counts.events, 18);

const bienalDates = corrected.events
  .filter((event) => /bienal/i.test(event.title))
  .map((event) => event.schedule.start.slice(0, 10))
  .sort();
assert.deepEqual(bienalDates, ["2026-08-19", "2026-08-20", "2026-08-21"]);
assert.match(corrected.events.find((event) => event.id === "agenda_pcdv_bienal_20260820").title, /La Fuga/);
assert.match(corrected.events.find((event) => event.id === "agenda_pcdv_bienal_20260821").title, /Estado #3/);

const rioja = corrected.events.filter((event) => event.source_id === "museo_palacio_rioja");
assert.equal(rioja.length, 15);
assert.ok(rioja.some((event) => event.id === "agenda_rioja_20260819_mitio" && event.schedule.start === "2026-08-19T16:00:00-04:00"));
assert.ok(rioja.some((event) => event.id === "agenda_rioja_20260820_visita_mar_dulce" && event.price.is_free === true));
assert.ok(rioja.some((event) => event.id === "agenda_rioja_20260825_angel"));
assert.ok(rioja.some((event) => event.id === "agenda_rioja_20260826_playtime"));
assert.ok(rioja.some((event) => event.id === "agenda_rioja_20260829_moncho"));

const repeated = applyEventDataCorrections(corrected);
assert.equal(repeated.events.length, 18, "correction must be idempotent");

console.log("event-data-corrections: ok");
