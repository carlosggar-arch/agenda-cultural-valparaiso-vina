import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  normalizeRootEventCategories,
} from "../assets/agenda-core.mjs";
import {
  rootEventMatchesCategories,
} from "../assets/root-combined-filter-core.mjs";

function event(overrides = {}) {
  return {
    id: "agenda_test",
    title: "Actividad",
    description: "",
    primary_category: { id: "cultura", label: "Cultura" },
    categories: [{ id: "cultura", label: "Cultura" }],
    location: { venue: "", city: "Valparaíso" },
    tags: [],
    ...overrides,
  };
}

test("Museos and Exposiciones become one public category", () => {
  const normalized = normalizeRootEventCategories(event({
    primary_category: { id: "museos", label: "Museos" },
    categories: [
      { id: "museos", label: "Museos" },
      { id: "exposiciones", label: "Exposiciones" },
    ],
  }));
  assert.deepEqual(normalized.categories, [
    { id: "exposiciones", label: "Exposiciones y museos" },
  ]);
  assert.equal(normalized.primary_category.id, "exposiciones");
});

test("Cultura disappears when another useful category already exists", () => {
  const normalized = normalizeRootEventCategories(event({
    categories: [
      { id: "cultura", label: "Cultura" },
      { id: "musica", label: "Música" },
    ],
  }));
  assert.deepEqual(normalized.categories, [{ id: "musica", label: "Música" }]);
  assert.equal(normalized.categories.some(({ id }) => id === "cultura"), false);
});

test("Cultura-only activities are redistributed by their content", () => {
  const normalized = normalizeRootEventCategories(event({
    title: "Charla y taller de patrimonio en el museo",
    description: "Encuentro con visita guiada y conversatorio.",
  }));
  assert.equal(normalized.categories.some(({ id }) => id === "cultura"), false);
  assert.equal(normalized.categories.some(({ id }) => id === "exposiciones"), true);
  assert.equal(normalized.categories.some(({ id }) => id === "cursos-talleres"), true);
});

test("Cultura-only activities without a clear signal fall back to Otros panoramas", () => {
  const normalized = normalizeRootEventCategories(event({ title: "Encuentro comunitario" }));
  assert.deepEqual(normalized.categories, [{ id: "otros", label: "Otros panoramas" }]);
});

test("combined category filtering treats Museos as Exposiciones", () => {
  const museum = event({
    primary_category: { id: "museos", label: "Museos" },
    categories: [{ id: "museos", label: "Museos" }],
  });
  assert.equal(rootEventMatchesCategories(museum, new Set(["exposiciones"])), true);
});

test("root layout compacting hides removed blocks and reduces top spacing", async () => {
  const source = await readFile(new URL("../assets/agenda-core.mjs", import.meta.url), "utf8");
  assert.match(source, /#explorar \.explore-heading/);
  assert.match(source, /#explorar \.section-tabs/);
  assert.match(source, /#categorias/);
  assert.match(source, /padding-top: \.75rem !important/);
});
