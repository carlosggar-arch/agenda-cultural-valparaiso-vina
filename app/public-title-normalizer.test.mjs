import assert from "node:assert/strict";
import { normalizePublicEventTitle } from "./public-title-normalizer.mjs";

const valpoTheatre = {
  primary_category: { id: "teatro", label: "Teatro" },
  categories: [{ id: "teatro", label: "Teatro" }],
  location: { venue: "Parque Cultural de Valparaíso", city: "Valparaíso" },
};

const gijonTheatre = {
  primary_category: { id: "teatro", label: "Teatro" },
  categories: [{ id: "teatro", label: "Teatro" }],
  location: { venue: "Teatro Jovellanos", city: "Gijón" },
};

const gijonExhibition = {
  primary_category: { id: "exposiciones", label: "Exposiciones" },
  categories: [{ id: "exposiciones", label: "Exposiciones" }],
  location: { venue: "Palacio de Revillagigedo", city: "Gijón" },
};

assert.equal(
  normalizePublicEventTitle('Teatro "Matriarcas: Poesía, Papel y Tinta"', valpoTheatre),
  "Matriarcas: Poesía, Papel y Tinta",
  "a redundant theatre label and decorative outer quotes must not be part of the public title",
);

assert.equal(
  normalizePublicEventTitle("TEATRO “MATRIARCAS: POESÍA, PAPEL Y TINTA”", valpoTheatre),
  "Matriarcas: Poesía, Papel y Tinta",
  "all-caps source titles must be normalized after removing the format label",
);

assert.equal(
  normalizePublicEventTitle("Exposición ''Convivium. Arqueología de la dieta mediterránea''", gijonExhibition),
  "Convivium. Arqueología de la dieta mediterránea",
  "duplicated decorative quotes from municipal feeds must be removed",
);

assert.equal(
  normalizePublicEventTitle("FETEN COMPAÑÍAS", gijonTheatre),
  "FETEN Compañías",
  "known acronyms must survive all-caps cleanup",
);

assert.equal(
  normalizePublicEventTitle("VII FESTIVAL DE MÚSICA", gijonTheatre),
  "VII Festival de Música",
  "roman numerals must survive all-caps cleanup",
);

assert.equal(
  normalizePublicEventTitle("CONCIERTO: NOCHE DE JAZZ", {
    primary_category: { id: "musica", label: "Música" },
    categories: [{ id: "musica", label: "Música" }],
    location: { venue: "Sala Acapulco", city: "Gijón" },
  }),
  "Noche de Jazz",
  "format labels separated from the actual name must be removed",
);

assert.equal(
  normalizePublicEventTitle("LA NOCHE DE JAZZ en GIJÓN", {
    primary_category: { id: "musica", label: "Música" },
    categories: [{ id: "musica", label: "Música" }],
    location: { venue: "Sala Acapulco", city: "Gijón" },
  }),
  "La Noche de Jazz",
  "mostly-uppercase titles with a lowercase connector must also be normalized",
);

assert.equal(
  normalizePublicEventTitle("GRAN FESTIVAL NAVIDEÑO Ballet y grandes invitados", valpoTheatre),
  "Gran Festival Navideño Ballet y grandes invitados",
  "an uppercase source prefix followed by normal mixed-case text must be normalized",
);

assert.equal(
  normalizePublicEventTitle("GRAN FESTIVAL NAVIDEÑO // Ballet y grandes invitados", valpoTheatre),
  "Gran festival navideño // Ballet y grandes invitados",
  "uppercase fragments separated with source-style double slashes must be normalized",
);

assert.equal(
  normalizePublicEventTitle("Concierto de Aranjuez", {
    primary_category: { id: "musica", label: "Música" },
    categories: [{ id: "musica", label: "Música" }],
    location: { venue: "Teatro Jovellanos", city: "Gijón" },
  }),
  "Concierto de Aranjuez",
  "a format word that genuinely belongs to the title must be preserved",
);

assert.equal(
  normalizePublicEventTitle("Teatro del absurdo", gijonTheatre),
  "Teatro del absurdo",
  "the word Teatro must be preserved when it is part of the actual title",
);

assert.equal(
  normalizePublicEventTitle('Las "otras" voces', valpoTheatre),
  'Las "otras" voces',
  "meaningful internal quotes must be preserved",
);

assert.equal(
  normalizePublicEventTitle('“La vida es sueño”', gijonTheatre),
  "La vida es sueño",
  "purely decorative outer quotes must be removed",
);

console.log("PUBLIC_TITLE_NORMALIZER_OK");
