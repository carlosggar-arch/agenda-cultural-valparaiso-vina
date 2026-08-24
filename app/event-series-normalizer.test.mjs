import assert from "node:assert/strict";
import test from "node:test";
import { normalizeEventSeries, PUBLIC_EVENT_SERIES_RULES } from "./event-series-normalizer.mjs";

function parent(occurrences) {
  return {
    id: "series",
    title: "Programación genérica",
    event_type: "event",
    source_id: "official-venue",
    links: { official: "https://venue.example/program" },
    schedule: { mode: "recurring", start: occurrences[0]?.start, end: occurrences.at(-1)?.start, occurrences },
    editorial: {},
  };
}

const rules = [{
  id: "declared-program",
  cityId: "test-city",
  match: { officialUrl: "https://venue.example/program/" },
  sessions: [
    { key: "a", title: "Repertorio A", start: "2026-08-29T19:00:00" },
    { key: "b", title: "Repertorio B", start: "2026-08-29T20:30:00" },
  ],
}];

test("expands a generic programme into concrete source-backed sessions", () => {
  const result = normalizeEventSeries({ counts: { total: 1, events: 1 }, events: [parent([
    { start: "2026-08-29T19:00:00+02:00", end: null },
    { start: "2026-08-29T20:30:00+02:00", end: null },
  ])] }, { cityId: "test-city", rules });
  assert.deepEqual(result.events.map((event) => event.title), ["Repertorio A", "Repertorio B"]);
  assert.deepEqual(result.events.map((event) => event.id), ["series__a", "series__b"]);
  assert.equal(result.events[0].editorial.event_family_id, "series");
  assert.equal(result.events[0].schedule.mode, "dated");
  assert.equal(result.counts.total, 2);
});

test("keeps the parent unchanged when any declared session lacks occurrence evidence", () => {
  const dataset = { counts: { total: 1, events: 1 }, events: [parent([
    { start: "2026-08-29T19:00:00+02:00", end: null },
  ])] };
  assert.equal(normalizeEventSeries(dataset, { cityId: "test-city", rules }), dataset);
});

test("does not leak a city series rule into another city", () => {
  const dataset = { events: [parent([
    { start: "2026-08-29T19:00:00+02:00" },
    { start: "2026-08-29T20:30:00+02:00" },
  ])] };
  assert.equal(normalizeEventSeries(dataset, { cityId: "other-city", rules }), dataset);
});

test("BIOPARC generic candlelight card becomes three repertoire cards without absorbing Disney", () => {
  const generic = {
    ...parent([
      { start: "2026-08-29T19:00:00", end: null },
      { start: "2026-08-29T20:30:00", end: null },
      { start: "2026-08-30T19:30:00", end: null },
    ]),
    id: "gijon_bioparc_acuario_gijon_4d750ccc7204740e",
    title: "Concierto piano a la luz de las velas",
    source_id: "bioparc_acuario_gijon",
    links: { official: "https://acuariogijon.es/actividad/concierto-piano-a-la-luz-de-las-velas/" },
  };
  const disney = {
    ...generic,
    id: "gijon_bioparc_acuario_gijon_c3aa7337a66721f9",
    title: "Concierto piano a la luz de las velas — Edición infantil",
    links: { official: "https://acuariogijon.es/actividad/concierto-piano-a-la-luz-de-las-velas-edicion-infantil/" },
  };
  const result = normalizeEventSeries({ events: [disney, generic] }, {
    cityId: "gijon",
    rules: PUBLIC_EVENT_SERIES_RULES,
  });
  assert.equal(result.events.length, 4);
  assert.equal(result.events.filter((event) => event.id === disney.id).length, 1);
  assert.deepEqual(result.events.slice(1).map((event) => event.schedule.start), [
    "2026-08-29T19:00:00",
    "2026-08-29T20:30:00",
    "2026-08-30T19:30:00",
  ]);
  assert.ok(result.events.every((event) => event.title !== "Concierto piano a la luz de las velas"));
});
