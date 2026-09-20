import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeAgendaCategories } from "./category-normalizer.js";

const fixtures = JSON.parse(readFileSync(
  new URL("../shared/editorial-category-evidence-fixtures.json", import.meta.url), "utf8",
));
for (const fixture of fixtures.cases) {
  const input = structuredClone(fixture.event);
  const original = structuredClone(input);
  const first = normalizeAgendaCategories({ events: [input] }).events[0];
  const second = normalizeAgendaCategories({ events: [first] }).events[0];
  assert.equal(first.primary_category.id, fixture.category, `${fixture.name}: category`);
  assert.deepEqual(second.semantics, first.semantics, `${fixture.name}: stable complete semantics`);
  assert.deepEqual(input, original, `${fixture.name}: immutable source evidence`);
  for (const field of ["category_evidence_text", "producer"]) {
    if (Object.hasOwn(input.semantics || {}, field)) {
      assert.deepEqual(first.semantics[field], input.semantics[field], `${fixture.name}: ${field}`);
    }
  }
}
console.log(`EDITORIAL_CATEGORY_EVIDENCE_OK cases=${fixtures.cases.length}`);
