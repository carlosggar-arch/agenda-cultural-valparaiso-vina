import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolvePublicCategory } from "../public-category-rules.mjs";
import { categoryFallbackImage } from "../image-resolver-core.mjs";

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

const appCore = readFileSync(new URL("../app-core.js", import.meta.url), "utf8");
const exhibitionGroups = readFileSync(new URL("../exhibition-groups.js", import.meta.url), "utf8");
const exhibitionGroupCore = readFileSync(new URL("../exhibition-group-core.mjs", import.meta.url), "utf8");
assert.match(appCore, /function buildDatedItems\(/);
assert.match(appCore, /card\.dataset\.eventGroup/);
assert.match(exhibitionGroups, /function enhanceCoreGroups\(/);
assert.match(exhibitionGroups, /groupStandaloneExhibitions/);
assert.match(exhibitionGroups, /function reconcileCommonMembership\(/);
assert.doesNotMatch(exhibitionGroups, /const\s+EXHIBITION_GROUP_MIN\s*=|function\s+clusterVenueExhibitions/);
assert.match(exhibitionGroupCore, /export const EXHIBITION_GROUP_MIN = 2/);
assert.match(exhibitionGroupCore, /exhibitionGroupingVenueKey/);
assert.match(exhibitionGroups, /categoryFallbackImage/);
assert.equal(categoryFallbackImage(null, { categoryHint: "exposiciones" }).url, "../assets/categoria-exposiciones.jpg");
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
