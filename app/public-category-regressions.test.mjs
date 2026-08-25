import assert from "node:assert/strict";
import { resolvePublicCategory } from "./public-category-rules.mjs";

function event(title, primary, { tags = [], description = "", venue = "" } = {}) {
  return {
    title,
    primary_category: { id: primary, label: primary },
    categories: [{ id: primary, label: primary }],
    tags,
    description,
    location: { venue, city: "Gijón" },
  };
}

function expectCategory(name, value, expected) {
  assert.equal(resolvePublicCategory(value).id, expected, name);
}

expectCategory("Matriarcas", event(
  'Teatro "Matriarcas: Poesía, Papel y Tinta"',
  "teatro",
  { tags: ["Teatro"], description: "Obra sobre Gabriela Mistral, Alfonsina Storni, poesía y literatura latinoamericana." },
), "teatro");
expectCategory("DIFERENCIAS", event("'DIFERENCIAS', de ENSEMBLE DUOPLUS", "teatro", { tags: ["Música"] }), "musica");
expectCategory("GLORIA", event("¡GLORIA!", "teatro", { tags: ["Teatro Jovellanos", "Clásica"], venue: "Teatro Jovellanos" }), "musica");
expectCategory("Mardi", event("MARDI JASS PARTY | LOS GRANDES DEL GOSPEL", "teatro", { tags: ["Teatro Jovellanos", "Música"], venue: "Teatro Jovellanos" }), "musica");
expectCategory("Spirits", event("SPIRITS OF NEW ORLEANS GOSPEL CHOIR | LOS GRANDES DEL GOSPEL", "teatro", { tags: ["Teatro Jovellanos", "Música"], venue: "Teatro Jovellanos" }), "musica");
expectCategory("High School Musical", event(
  "High School Musical Sing Along (2006)",
  "cine",
  { tags: ["Cine", "Función"], description: "Función confirmada por Cine Arte Viña del Mar. Categoría: Cine." },
), "cine");
expectCategory("A CUATRO MANOS", event("A CUATRO MANOS", "teatro", { tags: ["Teatro Jovellanos", "Teatro", "Clásica"], venue: "Teatro Jovellanos" }), "musica");
expectCategory("stage musical", event("Comedia musical familiar", "cultura"), "teatro");
expectCategory("music tag does not steal explicit stage musical", event("Obra Teatro Musical - Nemesio Pelao: ¿Qué es lo que te ha pasao?", "teatro", { tags: ["Música"] }), "teatro");
expectCategory("venue neutral", event("Concierto de cuarteto", "cultura", { venue: "Teatro Jovellanos" }), "musica");
console.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");
