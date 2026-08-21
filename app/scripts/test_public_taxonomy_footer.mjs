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

const museumBookPresentation = {
  title: "Presentación libro // “Decadencia”",
  primary_category: { id: "cultura", label: "Cultura" },
  description: "Actividad cultural confirmada en la cartelera municipal.",
  organizer: "Museo Palacio Rioja",
  source_name: "Museo Palacio Rioja",
  tags: ["Museo Palacio Rioja", "Visita Viña"],
};
assert.deepEqual(resolvePublicCategory(museumBookPresentation), { id: "otros", label: "Otros panoramas" });

const museumGuidedExhibition = {
  title: "Visita guiada exposición // “A veces un mar dulce”",
  primary_category: { id: "cultura", label: "Cultura" },
  organizer: "Museo Palacio Rioja",
};
assert.deepEqual(resolvePublicCategory(museumGuidedExhibition), { id: "exposiciones", label: "Exposiciones" });

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

for (const sample of [cultureCinema, cultureTheatre, cultureExhibition, museumBookPresentation, museumGuidedExhibition, genericCulture, museum]) {
  assert.notEqual(resolvePublicCategory(sample).label, "Cultura");
}

const exhibitionGroups = readFileSync(new URL("../exhibition-groups.js", import.meta.url), "utf8");
assert.match(exhibitionGroups, /groupStandaloneExhibitions/);
assert.match(exhibitionGroups, /FALLBACK_IMAGE[\s\S]*categoria-exposiciones\.jpg/);
assert.match(exhibitionGroups, /grouped-exhibition-item/);

const footer = readFileSync(new URL("../footer-credit.js", import.meta.url), "utf8");
assert.match(footer, /Carlos García García/);
assert.match(footer, /vivamos-footer-contact/);
assert.match(footer, /vivamos-contact-dialog/);
assert.match(footer, /formsubmit\.co\/ajax\/carlosggar@gmail\.com/);
assert.match(footer, /carlos\.garcia@usm\.cl/);
assert.match(footer, /_cc/);
assert.match(footer, /_replyto/);
assert.match(footer, /Enviar mensaje/);
assert.match(footer, /globalThis\.__VIVAMOS_RELEASE__/);
assert.match(footer, /PWA v\$\{release\}/);
assert.doesNotMatch(footer, /version\.textContent\s*=\s*"PWA"\s*;/);
assert.doesNotMatch(footer, /\["GitHub"/);
assert.doesNotMatch(footer, /\["Fuentes"/);
assert.doesNotMatch(footer, /vivamos-footer-link--secondary/);

console.log("PUBLIC_TAXONOMY_FOOTER_CONTRACT_OK");
