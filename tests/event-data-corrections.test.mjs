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
assert.equal(corrected.events.length, 3);
assert.equal(corrected.counts.total, 3);
assert.equal(corrected.counts.events, 3);
assert.deepEqual(
  corrected.events.map((event) => event.schedule.start.slice(0, 10)).sort(),
  ["2026-08-19", "2026-08-20", "2026-08-21"],
);
assert.match(corrected.events.find((event) => event.schedule.start.startsWith("2026-08-20")).title, /La Fuga/);
assert.match(corrected.events.find((event) => event.schedule.start.startsWith("2026-08-21")).title, /Estado #3/);

const repeated = applyEventDataCorrections(corrected);
assert.equal(repeated.events.length, 3, "correction must be idempotent");

console.log("event-data-corrections: ok");
