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
assert.equal(canonicalPublicCategoryId({ id: "otros", label: "Otros panoramas" }), "unclassified");
assert.equal(canonicalPublicCategoryId({ id: "charlas-conferencias" }), "charlas-conferencias");
assert.equal(canonicalPublicCategoryId({ label: "Conferencia" }), "charlas-conferencias");
assert.equal(canonicalPublicCategoryId({ id: "literatura" }), "literatura");
assert.equal(isPublicCategoryInGroup({ id: "cursos-talleres" }, "training"), true);
assert.equal(isPublicCategoryInGroup({ label: "Cursos, talleres y experiencias" }, "training"), true);
assert.equal(isPublicCategoryInGroup({ id: "exposiciones" }, "training"), false);
assert.equal(isPublicCategoryInGroup({ id: "charlas-conferencias" }, "talk"), true);
assert.equal(isPublicCategoryInGroup({ id: "literatura" }, "literature"), true);
assert.equal(publicCategorySymbol({ id: "cursos-talleres-campus" }), "✦");
assert.equal(publicCategorySymbol({ id: "naturaleza-montana" }), "⌁");
assert.equal(publicCategorySymbol({ id: "deportes" }), "●");
assert.equal(publicEventTypeLabel("program"), "Programa");
assert.equal(publicEventTypeLabel("registration_period"), "Inscripción");

// Generic public format rules: venue/source categories never decide these cases.
assert.deepEqual(
  resolvePublicCategory({
    title: "Xornaes Culturales Asturies en Guerra - 90 años: La Batalla por Gijón",
    primary_category: { id: "cultura", label: "Cultura" },
    venue: { name: "Centro Municipal Integrado" },
  }),
  { id: "charlas-conferencias", label: "Charlas y conferencias" },
);
assert.deepEqual(
  resolvePublicCategory({
    title: "Conferencia: Unidad y cohesión social ante los riesgos que corren",
    primary_category: { id: "cultura", label: "Cultura" },
  }),
  { id: "charlas-conferencias", label: "Charlas y conferencias" },
);
assert.deepEqual(
  resolvePublicCategory({
    title: "Presentación del Libro: Mariposa de la noche",
    primary_category: { id: "literatura-charlas-encuentros", label: "Literatura, charlas y encuentros" },
  }),
  { id: "literatura", label: "Literatura" },
);
assert.deepEqual(
  resolvePublicCategory({
    title: "El Arrebato. El viaje inesperado",
    primary_category: { id: "musica", label: "Música" },
    venue: { name: "Teatro de la Laboral" },
  }),
  { id: "musica", label: "Música" },
);
assert.deepEqual(
  resolvePublicCategory({
    title: "Melody. El bosque encantado",
    primary_category: { id: "musica", label: "Música" },
    venue: { name: "Teatro de la Laboral" },
  }),
  { id: "musica", label: "Música" },
);
assert.deepEqual(
  resolvePublicCategory({
    title: "Ángel Martín. Somos monos",
    primary_category: { id: "teatro", label: "Teatro / artes escénicas" },
    venue: { name: "Teatro de la Laboral" },
  }),
  { id: "teatro", label: "Teatro y danza" },
);
assert.deepEqual(
  resolvePublicCategory({
    title: "Concierto de cámara",
    primary_category: { id: "musica", label: "Música" },
    description: "Concierto seguido de una charla posterior con los intérpretes.",
  }),
  { id: "musica", label: "Música" },
);
assert.deepEqual(
  resolvePublicCategory({
    title: "Una noche especial",
    primary_category: { id: "actividad-panorama", label: "Actividad / panorama" },
    venue: { name: "Teatro de la Laboral" },
    description: "Apertura de puertas a las 20:00.",
  }),
  { id: "unclassified", label: "Otros panoramas" },
);

console.log("PUBLIC_CATEGORY_RULES_OK");
