import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { contentKindPresentation } from "./content-kind-presentation.mjs";

const registry = JSON.parse(await readFile(new URL("./cities.json", import.meta.url), "utf8"));
const valpo = registry.cities.find((city) => city.id === "valparaiso");
const gijon = registry.cities.find((city) => city.id === "gijon");

function event(overrides = {}) {
  return {
    title: "Actividad",
    event_type: "event",
    schedule: { start: "2026-08-23T19:00:00-04:00", end: null, occurrences: [] },
    ...overrides,
  };
}

test("dated event has one shared public meaning", () => {
  const presentation = contentKindPresentation(event(), valpo);
  assert.deepEqual(presentation, {
    kind: "dated_event",
    label: "Fecha concreta",
    detail: "Actividad con una fecha u horario concreto.",
  });
});

test("long running event is visually distinguished from one-date event", () => {
  const presentation = contentKindPresentation(event({
    schedule: { start: "2026-08-01", end: "2026-08-31", occurrences: [] },
  }), valpo);
  assert.equal(presentation.kind, "long_running_event");
  assert.equal(presentation.label, "En curso");
});

test("permanent and recurring opportunities are not presented as dated events", () => {
  const permanent = contentKindPresentation(event({
    event_type: "flexible_offer",
    schedule: { start: null, end: null, occurrences: [], display_text: "Horario flexible" },
  }), valpo);
  const recurring = contentKindPresentation(event({
    event_type: "recurring_offer",
    schedule: { start: null, end: null, occurrences: [], display_text: "Todos los sábados" },
  }), valpo);
  assert.equal(permanent.kind, "permanent_offer");
  assert.equal(permanent.label, "Disponible");
  assert.equal(recurring.kind, "recurring_offer");
  assert.equal(recurring.label, "Recurrente");
});

test("same content-kind presentation contract applies in Gijón", () => {
  const presentation = contentKindPresentation(event({
    schedule: { start: "2026-08-01", end: "2026-08-31", occurrences: [] },
  }), gijon);
  assert.equal(presentation.kind, "long_running_event");
  assert.equal(presentation.label, "En curso");
});

test("verified cultural calls have a distinct non-attendance presentation", () => {
  const presentation = contentKindPresentation(event({ content_kind: "call_for_submissions" }), valpo);
  assert.equal(presentation.kind, "call_for_submissions");
  assert.equal(presentation.label, "Convocatoria");
});
