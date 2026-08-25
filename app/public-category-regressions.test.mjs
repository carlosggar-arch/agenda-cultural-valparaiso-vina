import assert from "node:assert/strict";
import { resolvePublicCategory } from "./public-category-rules.mjs";

function event(title, primary, { tags = [], description = "", venue = "", city = "Gijón" } = {}) {
  return {
    title,
    primary_category: { id: primary, label: primary },
    categories: [{ id: primary, label: primary }],
    tags,
    description,
    location: { venue, city },
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
expectCategory("venue alias is semantic noise", event(
  "Lucy Briceño",
  "cultura",
  { description: "Lucy Briceño celebra su trayectoria con un concierto especial en el Teatro Mauri SCD.", venue: "Teatro Mauri SCD, Valparaíso", city: "Valparaíso" },
), "musica");
expectCategory("boleros valses and vinyl", event(
  "Viernes Cebolla",
  "cultura",
  { description: "Una noche de boleros y valses, seguida de baile en vinilo." },
), "musica");
expectCategory("flamenco typo and Gipsy Kings", event(
  "Mario Reyes Leyenda Gipsy",
  "cultura",
  { description: "Noche con Mario Reyes leyenda Gipsy Kings, tablao y baile flameno." },
), "musica");
expectCategory("venue phrase in title is semantic noise", event(
  "ESTOY BIEN EN TEATRO MAURI SCD VALPARAISO - GIRA NACIONAL",
  "cultura",
  { description: "Banda de punk rock presenta su nuevo disco y sus canciones en gira nacional.", venue: "Teatro Mauri SCD, Valparaíso", city: "Valparaíso" },
), "musica");
expectCategory("explicit concert beats incidental theatre venue wording", event(
  "Encuentro musical",
  "cultura",
  { description: "Este concierto se presenta en el primer teatro de la red y recorre canciones emblemáticas." },
), "musica");
expectCategory("figurative magic does not create theatre", event(
  "Viaje sonoro",
  "cultura",
  { description: "Un concierto de música chilena que recupera la magia de sus canciones." },
), "musica");
expectCategory("description genre reaches threshold", event(
  "Noche especial",
  "cultura",
  { description: "Una noche para bailar con clásicos del rock chileno." },
), "musica");
for (const sparseTitle of [
  "Carolina de la Muela en El Pasaje",
  "Aniversario Calathea Club",
  "CHAISENROOM | NO BRANDING NO NATION",
  "Sofía Alvez en El Pasaje",
  "Seba & El Monstruo, lanzamiento: Lleno de 97",
]) {
  expectCategory(`verified sparse PortalTickets music: ${sparseTitle}`, {
    ...event(sparseTitle, "cultura", { city: "Valparaíso" }),
    source_id: "portaltickets_valparaiso",
  }, "musica");
}
for (const sparseTitle of [
  "Esstelar Bday",
  "Special Anniversary Show Placebo 30 Años",
  "Previa Aniversario",
  "La Fiesta de Ritoque Fm",
]) {
  expectCategory(`verified sparse PortalTickets music event: ${sparseTitle}`, {
    ...event(sparseTitle, "cultura", { city: "Valparaíso" }),
    source_id: "portaltickets_valparaiso",
  }, "musica");
}
expectCategory("verified sparse PortalTickets fandom party", {
  ...event("Oshikatsu Party Oshifonda", "cultura", { city: "Valparaíso" }),
  source_id: "portaltickets_valparaiso",
}, "ferias-vida-local");
console.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");
