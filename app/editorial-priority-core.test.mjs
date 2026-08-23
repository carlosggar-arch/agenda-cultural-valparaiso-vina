import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { editorialPriority } from "./editorial-priority-core.mjs";
import { compareAgendaOrder, compareAgendaSemanticPriority } from "./agenda-order-core.mjs";

const registry = JSON.parse(await readFile(new URL("./cities.json", import.meta.url), "utf8"));
const valpo = registry.cities.find((city) => city.id === "valparaiso");
const gijon = registry.cities.find((city) => city.id === "gijon");
const NOW = new Date("2026-08-23T12:00:00-04:00");

function fixture(id, overrides = {}) {
  const event = {
    id,
    title: id,
    event_type: "event",
    primary_category: { id: "musica", label: "Música" },
    categories: [{ id: "musica", label: "Música" }],
    location: { venue: "Sala", city: "Viña del Mar", commune: "Viña del Mar" },
    schedule: { start: "2026-08-24T19:00:00-04:00", end: null, occurrences: [] },
    links: {},
    public_status: {},
  };
  return Object.assign(event, overrides);
}

test("editorial priority is transparent and factual", () => {
  const item = fixture("destacado", {
    links: { corroborating: "https://example.org/second-source" },
    public_status: { source_official: true, information_completeness: "complete" },
    editorial: { priority_flags: ["estreno"] },
  });
  const result = editorialPriority(item, valpo);
  assert.equal(result.score, 9);
  assert.deepEqual(result.signals, [
    "official_source",
    "corroborated_source",
    "complete_information",
    "one_day_event",
    "explicit_special_event",
  ]);
});

test("better documented event wins only after temporal semantics tie", () => {
  const plain = fixture("a-plain", { title: "A sin verificar" });
  const verified = fixture("z-verified", {
    title: "Z verificado",
    public_status: { source_official: true, information_completeness: "complete" },
  });
  assert.equal(compareAgendaSemanticPriority(plain, verified, valpo, NOW), 0);
  assert.ok(compareAgendaOrder(verified, plain, valpo, NOW) < 0);
});

test("editorial score can never make tomorrow outrank today", () => {
  const today = fixture("today", {
    schedule: { start: "2026-08-23T20:00:00-04:00", end: null, occurrences: [] },
  });
  const tomorrowFeatured = fixture("tomorrow-featured", {
    schedule: { start: "2026-08-24T10:00:00-04:00", end: null, occurrences: [] },
    links: { corroborating: "https://example.org/corroboration" },
    public_status: { source_official: true, information_completeness: "complete" },
    editorial: { flags: ["inauguración"] },
  });
  assert.ok(editorialPriority(tomorrowFeatured, valpo).score > editorialPriority(today, valpo).score);
  assert.ok(compareAgendaOrder(today, tomorrowFeatured, valpo, NOW) < 0);
});

test("same editorial semantics work in Gijón without city-specific weights", () => {
  const plain = fixture("plain-gijon", {
    location: { venue: "Sala", city: "Gijón", commune: "Gijón" },
    schedule: { start: "2026-08-24T19:00:00+02:00", end: null, occurrences: [] },
  });
  const official = fixture("official-gijon", {
    location: { venue: "Sala", city: "Gijón", commune: "Gijón" },
    schedule: { start: "2026-08-24T19:00:00+02:00", end: null, occurrences: [] },
    public_status: { source_official: true },
  });
  assert.equal(compareAgendaSemanticPriority(plain, official, gijon, NOW), 0);
  assert.ok(compareAgendaOrder(official, plain, gijon, NOW) < 0);
});
