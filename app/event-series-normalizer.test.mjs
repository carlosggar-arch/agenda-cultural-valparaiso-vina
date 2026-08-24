import assert from "node:assert/strict";
import test from "node:test";
import { normalizeEventSeries } from "./event-series-normalizer.mjs";

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
