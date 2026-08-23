import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildEventSemantics } from "./event-semantics.mjs";
import { normalizeAgendaCategories } from "./category-normalizer.js";
import { normalizeFormationCycles } from "./formation-cycle-classifier.js";

const fixtures = JSON.parse(
  readFileSync(new URL("../shared/event-semantics-fixtures.json", import.meta.url), "utf8"),
);

assert.equal(fixtures.schema_version, "1.0.0");
for (const fixture of fixtures.cases) {
  const semantics = buildEventSemantics(fixture.event);
  const expected = fixture.expected;
  assert.equal(semantics.category.id, expected.category, `${fixture.name}: category`);
  assert.equal(semantics.primary_domain, expected.primary_domain, `${fixture.name}: primary domain`);
  assert.deepEqual(
    semantics.secondary_domains,
    expected.secondary_domains,
    `${fixture.name}: secondary domains`,
  );
  assert.equal(semantics.format, expected.format, `${fixture.name}: format`);
  assert.equal(semantics.audience, expected.audience, `${fixture.name}: audience`);
  assert.equal(semantics.lifecycle, expected.lifecycle, `${fixture.name}: lifecycle`);
  assert.ok(Array.isArray(semantics.domain_candidates), `${fixture.name}: candidates`);
  assert.ok(Array.isArray(semantics.evidence), `${fixture.name}: evidence`);
}

const sourceEvent = {
  id: "source-provenance",
  title: "Concierto de jazz",
  primary_category: { id: "otros", label: "Otros panoramas" },
};
const once = normalizeAgendaCategories({ events: [sourceEvent] }).events[0];
const twice = normalizeAgendaCategories({ events: [once] }).events[0];
assert.equal(once.primary_category.id, "musica");
assert.equal(twice.primary_category.id, "musica");
assert.equal(once.semantics.source_category.id, "otros");
assert.equal(twice.semantics.source_category.id, "otros");
assert.equal(twice.semantics.score, once.semantics.score, "second pass must not self-amplify");
assert.deepEqual(twice.semantics.secondary_domains, once.semantics.secondary_domains);

const registration = normalizeAgendaCategories({
  events: [{
    id: "registration-lifecycle",
    title: "Taller de cerámica — inscripciones abiertas",
    description: "Proceso de inscripción para un taller de formación de temporada.",
    event_type: "event",
    primary_category: { id: "otros", label: "Otros panoramas" },
    schedule: {
      mode: "multi_day",
      start: "2026-08-01",
      end: "2026-09-01",
      occurrences: [],
    },
  }],
});
const lifecycleNormalized = normalizeFormationCycles(registration).events[0];
assert.equal(lifecycleNormalized.event_type, "registration_period");
assert.equal(lifecycleNormalized.lifecycle.state, "registration_period");
assert.equal(lifecycleNormalized.semantics.lifecycle, "registration_period");
assert.equal(lifecycleNormalized.semantics.primary_domain, "cursos-talleres-campus");

console.log("SHARED_EVENT_SEMANTICS_OK");
