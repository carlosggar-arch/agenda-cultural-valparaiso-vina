import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolvePublicCategory } from "../public-category-rules.mjs";

const cultureCinema = {
  title: "Ciclo de verano",
  primary_category: { id: "cultura", label: "Cultura" },
  tags: ["Audiovisual", "Cine"],
};
assert.deepEqual(resolvePublicCategory(cultureCinema), { id: "cine", label: "Cine" });

const cultureTheatre = {
  title: "Escena Xixón",
  primary_category: { id: "cultura", label: "Cultura" },
  tags: ["Artes escénicas", "Teatro", "Danza"],
};
assert.deepEqual(resolvePublicCategory(cultureTheatre), { id: "teatro", label: "Teatro" });

const cultureExhibition = {
  title: "Programa del museo",
  primary_category: { id: "cultura", label: "Cultura" },
  description: "Programa municipal de exposiciones y muestras temporales.",
};
assert.deepEqual(resolvePublicCategory(cultureExhibition), { id: "exposiciones", label: "Exposiciones" });

const genericCulture = {
  title: "CENTEX – Cartelera Agosto",
  primary_category: { id: "cultura", label: "Cultura" },
  description: "Programación cultural mensual del centro.",
};
assert.deepEqual(resolvePublicCategory(genericCulture), { id: "otros", label: "Otros panoramas" });

const museum = {
  title: "Muestra temporal",
  primary_category: { id: "museos", label: "Museos" },
};
assert.deepEqual(resolvePublicCategory(museum), { id: "exposiciones", label: "Exposiciones" });

for (const sample of [cultureCinema, cultureTheatre, cultureExhibition, genericCulture, museum]) {
  assert.notEqual(resolvePublicCategory(sample).label, "Cultura");
}

const compact = readFileSync(new URL("../exhibition-compact.js", import.meta.url), "utf8");
assert.match(compact, /GENERIC_EXHIBITION_FALLBACK/);
assert.match(compact, /categoria-exposiciones\.jpg/);

const footer = readFileSync(new URL("../footer-credit.js", import.meta.url), "utf8");
assert.match(footer, /Carlos García García/);
assert.match(footer, /github\.com\/carlosggar-arch/);
assert.match(footer, /Fuentes/);

console.log("PUBLIC_TAXONOMY_FOOTER_CONTRACT_OK");
