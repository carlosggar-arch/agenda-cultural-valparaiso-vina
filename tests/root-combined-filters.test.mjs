import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  filterRootEvents,
  normalizeRootSearchText,
  rootEventMatchesAdvancedFilters,
  rootEventMatchesQuery,
  rootEventPublicCategories,
} from "../assets/root-combined-filter-core.mjs";

const events = [
  {
    id: "jazz-valpo",
    title: "Concierto de Jazz del Puerto",
    description: "Música en vivo para todo público.",
    organizer: "Estrella Negra",
    source_name: "Estrella Negra Club de Jazz",
    categories: [{ id: "musica", label: "Música" }],
    location: { venue: "Club de Jazz", address: "Carrera, Valparaíso", city: "Valparaíso", online: false },
    audience: "Todo público",
    tags: ["jazz"],
    price: { is_free: false, display_text: "$8.000" },
    schedule: { display_text: "viernes 21:00" },
    links: { tickets: "https://example.test/tickets" },
    public_status: {},
  },
  {
    id: "taller-vina",
    title: "Taller infantil de grabado",
    description: "Actividad gratuita para niñas, niños y familias.",
    organizer: "Museo",
    source_name: "Museo",
    categories: [{ id: "cursos-talleres", label: "Cursos y talleres" }, { id: "artes-visuales", label: "Artes visuales" }],
    location: { venue: "Museo de Viña", city: "Viña del Mar", online: false },
    audience: "Familiar",
    tags: ["infantil"],
    price: { is_free: true, display_text: "Gratis" },
    schedule: { display_text: "sábado 11:00" },
    links: { registration: "https://example.test/registro" },
    public_status: { registration_open: true },
  },
  {
    id: "charla-online",
    title: "Charla de patrimonio",
    description: "Encuentro virtual con inscripción previa.",
    categories: [{ id: "cultura", label: "Cultura" }],
    location: { city: "Valparaíso", online: true },
    price: { is_free: true, display_text: "Liberado" },
    schedule: { display_text: "martes 18:00" },
    links: { registration: "https://example.test/register" },
    public_status: {},
  },
];

test("normalization is accent-insensitive", () => {
  assert.equal(normalizeRootSearchText("Música en Viña"), "musica en vina");
});

test("search uses AND tokens and useful aliases", () => {
  assert.equal(rootEventMatchesQuery(events[0], "jazz valpo"), true);
  assert.equal(rootEventMatchesQuery(events[1], "familiar gratis vina"), true);
  assert.equal(rootEventMatchesQuery(events[2], "online inscripcion gratis"), true);
  assert.equal(rootEventMatchesQuery(events[0], "jazz vina"), false);
});

test("combined dimensions apply together", () => {
  const result = filterRootEvents(events, {
    query: "familiar",
    categories: new Set(["cursos-talleres", "musica"]),
    access: "inscripcion",
    format: "presencial",
    audience: "familiar",
    price: "gratis",
  });
  assert.deepEqual(result.map((event) => event.id), ["taller-vina"]);
});

test("multiple selected categories are OR while each event has one normalized public category", () => {
  assert.equal(rootEventMatchesAdvancedFilters(events[0], {
    categories: new Set(["musica", "cursos-talleres"]),
    access: "entradas",
    format: "presencial",
    price: "pagado",
  }), true);
  assert.deepEqual(rootEventPublicCategories(events[2]), [
    { id: "otros", label: "Otros panoramas" },
  ]);
  assert.equal(rootEventMatchesAdvancedFilters(events[2], {
    categories: new Set(["musica", "otros"]),
    access: "inscripcion",
  }), true);
  assert.equal(rootEventPublicCategories(events[1]).length, 1);
});

test("Museos and Exposiciones share one public category", () => {
  const museum = {
    id: "museo",
    title: "Visita al museo",
    primary_category: { id: "museos", label: "Museos" },
    categories: [
      { id: "museos", label: "Museos" },
      { id: "exposiciones", label: "Exposiciones" },
    ],
  };
  assert.deepEqual(rootEventPublicCategories(museum), [
    { id: "exposiciones", label: "Exposiciones y museos" },
  ]);
  assert.equal(rootEventMatchesAdvancedFilters(museum, {
    categories: new Set(["exposiciones"]),
  }), true);
});

test("Cultura is resolved to one APP-style public category and is no longer public", () => {
  const culture = {
    id: "culture",
    title: "Charla y taller de patrimonio en el museo",
    description: "Conversatorio y visita guiada.",
    primary_category: { id: "cultura", label: "Cultura" },
    categories: [{ id: "cultura", label: "Cultura" }],
    location: { venue: "Museo" },
  };
  assert.deepEqual(rootEventPublicCategories(culture), [
    { id: "cursos-talleres", label: "Cursos y talleres" },
  ]);
});

test("ambiguous Cultura falls back to Otros panoramas", () => {
  const categories = rootEventPublicCategories({
    id: "culture-generic",
    title: "Encuentro comunitario",
    primary_category: { id: "cultura", label: "Cultura" },
    categories: [{ id: "cultura", label: "Cultura" }],
  });
  assert.deepEqual(categories, [{ id: "otros", label: "Otros panoramas" }]);
});

test("non-canonical source categories are folded into the stable public taxonomy", () => {
  assert.deepEqual(rootEventPublicCategories({
    id: "visual",
    title: "Muestra de fotografía contemporánea",
    primary_category: { id: "artes-visuales", label: "Artes visuales" },
    categories: [{ id: "artes-visuales", label: "Artes visuales" }],
  }), [{ id: "exposiciones", label: "Exposiciones y museos" }]);
});

test("Los Fantasmas is discoverable through Teatro even before the raw dataset republishes", () => {
  const losFantasmas = {
    id: "agenda_bc147abef119a17edb8a9770",
    title: "Los Fantasmas",
    categories: [{ id: "cine", label: "Cine" }],
    primary_category: { id: "cine", label: "Cine" },
    location: { venue: "Centro de Investigación Teatro La Peste", city: "Valparaíso", online: false },
    price: { is_free: true, display_text: "Gratis" },
    schedule: { display_text: "22-08-2026 · 22:00" },
    links: {},
    public_status: {},
  };
  assert.deepEqual(rootEventPublicCategories(losFantasmas), [{ id: "teatro", label: "Teatro" }]);
  assert.equal(rootEventMatchesAdvancedFilters(losFantasmas, {
    categories: new Set(["teatro"]),
  }), true);
  assert.equal(rootEventMatchesQuery(losFantasmas, "teatro"), true);
});

test("root page loads the advanced filter layer through existing enhancements", async () => {
  const enhancements = await readFile(new URL("../assets/web-event-enhancements.js", import.meta.url), "utf8");
  const browserLayer = await readFile(new URL("../assets/root-combined-filters.js", import.meta.url), "utf8");
  const css = await readFile(new URL("../assets/root-combined-filters.css", import.meta.url), "utf8");
  assert.match(enhancements, /root-combined-filters\.js/);
  assert.match(browserLayer, /data-advanced-query/);
  assert.match(browserLayer, /data-advanced-categories/);
  assert.match(browserLayer, /data-advanced-access/);
  assert.match(browserLayer, /data-advanced-format/);
  assert.match(browserLayer, /data-advanced-audience/);
  assert.match(css, /event-card\[hidden\]/);
});

test("root homepage hides the agenda heading and section tabs", async () => {
  const css = await readFile(new URL("../assets/accessibility.css", import.meta.url), "utf8");
  assert.match(css, /#explorar\s+\.explore-heading/);
  assert.match(css, /#explorar\s+\.section-tabs/);
});

test("root homepage places the quick navigation after category shortcuts", async () => {
  const enhancements = await readFile(new URL("../assets/web-event-enhancements.js", import.meta.url), "utf8");
  assert.match(enhancements, /function placePrimaryNavigationAfterCategories/);
  assert.match(enhancements, /document\.querySelector\("\.primary-navigation"\)/);
  assert.match(enhancements, /document\.querySelector\("\.category-section"\)/);
  assert.match(enhancements, /categories\.after\(navigation\)/);
  assert.match(enhancements, /placePrimaryNavigationAfterCategories\(\)/);
});

test("root homepage rebuilds normalized category controls, category badges and compact spacing", async () => {
  const enhancements = await readFile(new URL("../assets/web-event-enhancements.js", import.meta.url), "utf8");
  const core = await readFile(new URL("../assets/root-combined-filter-core.mjs", import.meta.url), "utf8");
  assert.match(enhancements, /function installPublicCategoryUi/);
  assert.match(enhancements, /function applyCategoryPresentation/);
  assert.match(enhancements, /\.pill-category/);
  assert.match(enhancements, /rootEnhancementsVersion/);
  assert.match(core, /function resolveRootPublicCategory/);
  assert.match(core, /Exposiciones y museos/);
  assert.match(enhancements, /__VIVAMOS_ROOT_FILTERS__/);
  assert.match(enhancements, /padding-bottom: \.65rem !important/);
  assert.match(enhancements, /padding-top: \.7rem !important/);
});