import assert from "node:assert/strict";
import { normalizePublicEventTitle } from "./public-title-normalizer.mjs";

const music = {
  primary_category: { id: "musica", label: "Música" },
  categories: [{ id: "musica", label: "Música" }],
  location: { venue: "Sala Acapulco", city: "Gijón" },
};
const theatre = {
  primary_category: { id: "teatro", label: "Teatro" },
  categories: [{ id: "teatro", label: "Teatro" }],
  location: { venue: "Teatro Jovellanos", city: "Gijón" },
};
const training = {
  primary_category: { id: "cursos-talleres-campus", label: "Cursos, talleres y experiencias" },
  categories: [{ id: "cursos-talleres-campus", label: "Cursos, talleres y experiencias" }],
  location: { venue: "Centro Cultural", city: "Gijón" },
};

assert.equal(
  normalizePublicEventTitle("NO TE LO PIERDAS: CONCIERTO: NOCHE DE JAZZ", music),
  "Noche de Jazz",
);
assert.equal(normalizePublicEventTitle("¡IMPERDIBLE! “La vida es sueño”", theatre), "La vida es sueño");
assert.equal(normalizePublicEventTitle("Taller de cerámica — ÚLTIMOS CUPOS", theatre), "Taller de cerámica");
assert.equal(
  normalizePublicEventTitle("IMPERDIBLE — ÚLTIMAS ENTRADAS — NOCHE DE JAZZ", music),
  "Noche de Jazz",
);
assert.equal(
  normalizePublicEventTitle("Imperdible obra de Alfredo Castro", theatre),
  "Imperdible obra de Alfredo Castro",
  "promotional words inside a semantic title must be preserved",
);
assert.equal(
  normalizePublicEventTitle("Noche de jazz — Teatro Jovellanos", theatre),
  "Noche de jazz",
  "the exact canonical venue suffix must be removed",
);
assert.equal(
  normalizePublicEventTitle("Noche de jazz — Teatro Jovellanos, Gijón", theatre),
  "Noche de jazz",
  "the canonical venue plus city suffix must be removed",
);
assert.equal(
  normalizePublicEventTitle("Noche de jazz — Jovellanos", theatre),
  "Noche de jazz — Jovellanos",
  "partial venue aliases must not be stripped from suffixes",
);
assert.equal(
  normalizePublicEventTitle("Noche de jazz — Gijón", theatre),
  "Noche de jazz",
  "the existing exact city-suffix cleanup must remain available",
);
assert.equal(
  normalizePublicEventTitle("Ciclo de talleres: CERÁMICA PARA PRINCIPIANTES", training),
  "Cerámica para principiantes",
  "the canonical shared training category must use the existing title cleanup",
);

for (const [input, event] of [
  ["NO TE LO PIERDAS: CONCIERTO: NOCHE DE JAZZ", music],
  ["Noche de jazz — Teatro Jovellanos", theatre],
  ["Taller de cerámica — ÚLTIMOS CUPOS", theatre],
]) {
  const once = normalizePublicEventTitle(input, event);
  assert.equal(normalizePublicEventTitle(once, event), once, `normalization must be idempotent for ${input}`);
}

console.log("PUBLIC_TITLE_NORMALIZER_POINT7_OK");
