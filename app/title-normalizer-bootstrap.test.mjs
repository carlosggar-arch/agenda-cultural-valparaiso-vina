import assert from "node:assert/strict";
import { normalizeAgendaTitles, recoverAgendaTitles } from "./title-normalizer-bootstrap.js";

const dataset = {
  city: "gijon",
  events: [
    {
      id: "changed",
      title: "NO TE LO PIERDAS: CONCIERTO: NOCHE DE JAZZ",
      primary_category: { id: "musica", label: "Música" },
      categories: [{ id: "musica", label: "Música" }],
      location: { venue: "Sala Acapulco", city: "Gijón" },
    },
    {
      id: "existing-original",
      title: "IMPERDIBLE — La vida es sueño",
      original_title: "FUENTE MÁS ANTIGUA: La vida es sueño",
      primary_category: { id: "teatro", label: "Teatro" },
      categories: [{ id: "teatro", label: "Teatro" }],
      location: { venue: "Teatro Jovellanos", city: "Gijón" },
    },
    {
      id: "unchanged",
      title: "Concierto de Aranjuez",
      primary_category: { id: "musica", label: "Música" },
      categories: [{ id: "musica", label: "Música" }],
      location: { venue: "Teatro Jovellanos", city: "Gijón" },
    },
  ],
};

const once = normalizeAgendaTitles(dataset);
assert.equal(once.events[0].title, "Noche de Jazz");
assert.equal(once.events[0].original_title, dataset.events[0].title, "changed titles must preserve the incoming source title");
assert.equal(once.events[1].title, "La vida es sueño");
assert.equal(once.events[1].original_title, "FUENTE MÁS ANTIGUA: La vida es sueño", "existing provenance must never be overwritten");
assert.equal(Object.hasOwn(once.events[2], "original_title"), false, "unchanged titles must not invent provenance");

const twice = normalizeAgendaTitles(once);
assert.deepEqual(twice, once, "dataset title normalization must be idempotent");

const gijonRecovered = recoverAgendaTitles({
  city: "gijon",
  events: [{
    id: "agenda-gijon-caption-fragment",
    title: "00 y las 07:30h, La Sala emite el relato sonoro, cuyo desenlace se descubre visitando la instalación",
    description: "Cápsula Radio: “La tercera luz”, de Alberto Conejero. Instalación de ficción sonora. Proyecto de Coma14 + Société Mouffette.",
    source_id: "agenda_gijon",
    source_name: "Agenda Gijón",
    location: { venue: "Primera planta del Antiguo Instituto Jovellanos", city: "Gijón" },
  }],
});
assert.equal(gijonRecovered.events[0].title, "Cápsula Radio: La tercera luz");
assert.equal(gijonRecovered.events[0].editorial.title_original.startsWith("00 y las 07:30h"), true);
assert.equal(gijonRecovered.events[0].editorial.category_recovery_hint, "exposiciones");

console.log("TITLE_NORMALIZER_BOOTSTRAP_POINT7_OK");
