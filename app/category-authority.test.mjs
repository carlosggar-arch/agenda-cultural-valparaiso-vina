import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { canonicalPublicCategory } from "./public-category-rules.mjs";

const taxonomy = JSON.parse(readFileSync(new URL("../shared/public-category-taxonomy.json", import.meta.url), "utf8"));
const core = readFileSync(new URL("./app-core.js", import.meta.url), "utf8");
const combined = readFileSync(new URL("./combined-filters.js", import.meta.url), "utf8");

const expectedAliases = {
  museos: "exposiciones",
  "artes-visuales-museo": "exposiciones",
  "cursos-talleres": "cursos-talleres-campus",
  deportes: "naturaleza-deportes",
  gastronomia: "ferias-gastronomia",
  "teatro-artes-escenicas": "teatro",
};

for (const [alias, canonical] of Object.entries(expectedAliases)) {
  assert.equal(taxonomy.aliases[alias], canonical, `${alias} alias must live in shared taxonomy`);
  assert.equal(canonicalPublicCategory({ id: alias, label: alias })?.id, canonical, `${alias} must resolve through shared taxonomy`);
}
assert.deepEqual(canonicalPublicCategory({ id: "museos", label: "Museos" }), {
  id: "exposiciones",
  label: "Exposiciones",
});

for (const [name, source] of [["app-core", core], ["combined-filters", combined]]) {
  assert.match(source, /canonicalPublicCategory/, `${name} must consume the shared category authority`);
  assert.doesNotMatch(source, /MUSEUM_CATEGORY_ID/, `${name} must not declare a museum alias constant`);
  assert.doesNotMatch(source, /id\s*===\s*["']museos["']/, `${name} must not implement museos remapping`);
  assert.doesNotMatch(source, /id\s*=\s*["']exposiciones["']/, `${name} must not assign canonical categories locally`);
}

console.log("SINGLE_PUBLIC_CATEGORY_AUTHORITY_OK");
