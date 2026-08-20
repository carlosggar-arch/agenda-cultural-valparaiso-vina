import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  filterRootEvents,
  normalizeRootSearchText,
  rootEventMatchesAdvancedFilters,
  rootEventMatchesQuery,
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

test("multiple categories are OR within category and AND with other dimensions", () => {
  assert.equal(rootEventMatchesAdvancedFilters(events[0], {
    categories: new Set(["musica", "cursos-talleres"]),
    access: "entradas",
    format: "presencial",
    price: "pagado",
  }), true);
  assert.equal(rootEventMatchesAdvancedFilters(events[2], {
    categories: new Set(["musica", "cursos-talleres"]),
    access: "inscripcion",
  }), false);
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
