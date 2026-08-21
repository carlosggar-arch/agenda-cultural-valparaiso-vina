import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  canonicalPublicCategoryId,
  isPublicCategoryInGroup,
  publicCategorySymbol,
  publicEventTypeLabel,
  resolvePublicCategory,
} from "./public-category-rules.mjs";

const fixturesUrl = new URL("../shared/public-category-fixtures.json", import.meta.url);
const fixtures = JSON.parse(readFileSync(fileURLToPath(fixturesUrl), "utf8"));

for (const fixture of fixtures.cases) {
  assert.deepEqual(
    resolvePublicCategory(fixture.event),
    fixture.expected,
    `shared fixture failed: ${fixture.name}`,
  );
}

assert.equal(canonicalPublicCategoryId({ id: "formacion-taller", label: "Formación / taller" }), "cursos-talleres-campus");
assert.equal(canonicalPublicCategoryId({ id: "museos", label: "Museos" }), "exposiciones");
assert.equal(canonicalPublicCategoryId({ label: "Cursos, talleres y experiencias" }), "cursos-talleres-campus");
assert.equal(canonicalPublicCategoryId({ id: "cursos-talleres-experiencias" }), "cursos-talleres-campus");
assert.equal(isPublicCategoryInGroup({ id: "cursos-talleres" }, "training"), true);
assert.equal(isPublicCategoryInGroup({ label: "Cursos, talleres y experiencias" }, "training"), true);
assert.equal(isPublicCategoryInGroup({ id: "exposiciones" }, "training"), false);
assert.equal(publicCategorySymbol({ id: "cursos-talleres-campus" }), "✦");
assert.equal(publicCategorySymbol({ id: "naturaleza-deportes" }), "⌁");
assert.equal(publicEventTypeLabel("program"), "Programa");
assert.equal(publicEventTypeLabel("registration_period"), "Inscripción");

console.log("PUBLIC_CATEGORY_RULES_OK");
