import assert from "node:assert/strict";
import { resolvePublicCategory } from "./public-category-rules.mjs";

const expected = { id: "cursos-talleres-campus", label: "Cursos, talleres y campus" };

assert.deepEqual(resolvePublicCategory({
  title: "Campus de Verano de la Laboral 2026",
  event_type: "event",
  primary_category: { id: "formacion-taller", label: "Formación / taller" },
}), expected, "legacy Formación / taller must merge into the shared category");

assert.deepEqual(resolvePublicCategory({
  title: "Gijón Verano: inscripciones",
  event_type: "program",
  primary_category: { id: "cultura", label: "Cultura" },
}), expected, "summer programme registrations must not be classified as sport");

assert.deepEqual(resolvePublicCategory({
  title: "II Ciclo de Formación Cultural",
  event_type: "event",
  primary_category: { id: "cultura", label: "Cultura" },
  tags: ["formación", "taller"],
}), expected, "Viña formation and workshop activities must use the shared category");

assert.deepEqual(resolvePublicCategory({
  title: "Taller de Liderazgo Prosocial para Agentes de Cambio",
  event_type: "event",
  primary_category: { id: "cursos-talleres", label: "Cursos y talleres" },
}), expected, "the previous Cursos y talleres category must be migrated to the shared category");

assert.deepEqual(resolvePublicCategory({
  title: "Salida de senderismo de verano",
  event_type: "event",
  primary_category: { id: "naturaleza-deportes", label: "Naturaleza y deportes" },
}), { id: "naturaleza-deportes", label: "Naturaleza y deportes" }, "a concrete outdoor activity must keep its specific category");

console.log("PUBLIC_CATEGORY_RULES_OK");
