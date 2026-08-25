import assert from "node:assert/strict";
import { resolvePublicCategory } from "./public-category-rules.mjs";
import { deduplicateCrossSourceDataset } from "./cross-source-deduplication.mjs";

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
const matriarcasLiteratureDescription = "Matriarcas es una obra sobre Gabriela Mistral, Alfonsina Storni y Juana de Ibarbourou, literatura latinoamericana, poesía, poetas y una histórica conferencia literaria.";
const matriarcasPcdv = {
  ...event("Matriarcas: Poesía, Papel y Tinta", "teatro", {
    description: matriarcasLiteratureDescription,
    venue: "Parque Cultural de Valparaíso",
    city: "Valparaíso",
  }),
  id: "pcdv-matriarcas",
  source_id: "pcdv",
  source_name: "Parque Cultural de Valparaíso",
  source_url: "https://parquecultural.cl/matriarcas",
  schedule: { start: "2026-08-28T19:00:00-04:00", end: "2026-08-28T19:00:00-04:00" },
  public_status: { source_official: true, information_completeness: "complete" },
  semantics: {
    primary_domain: "teatro",
    confidence: "high",
    score: 230,
    source_category: { id: "teatro", label: "Teatro y danza" },
  },
};
const matriarcasPortal = {
  ...event("Matriarcas", "teatro", {
    description: matriarcasLiteratureDescription,
    venue: "Parque Cultural de Valparaíso",
    city: "Valparaíso",
  }),
  id: "portal-matriarcas",
  source_id: "portaltickets_valparaiso",
  source_name: "PortalTickets — Región de Valparaíso",
  source_url: "https://www.portaltickets.cl/evento/matriarcas",
  schedule: { start: "2026-08-28T19:00:00-04:00", end: "2026-08-28T19:00:00-04:00" },
  public_status: { source_official: false, information_completeness: "complete" },
  semantics: {
    primary_domain: "teatro",
    confidence: "low",
    score: 40,
    source_category: { id: "cultura", label: "Cultura" },
  },
};
const matriarcasDeduped = deduplicateCrossSourceDataset({
  events: [matriarcasPcdv, matriarcasPortal],
  counts: { total: 2, events: 2, courses: 0, flexible_offers: 0, programs: 0 },
});
assert.equal(matriarcasDeduped.events.length, 1, "Matriarcas duplicates must reconcile");
assert.equal(matriarcasDeduped.events[0].primary_category?.id, "teatro", "dedup must preserve agreed Teatro classification");
assert.equal(matriarcasDeduped.events[0].editorial?.merged_category_evidence?.length, 2, "dedup must retain both pre-merge category observations");

expectCategory("merged category consensus beats prose-topic drift", {
  ...event("Matriarcas: Poesía, Papel y Tinta", "teatro", {
    description: matriarcasLiteratureDescription,
    venue: "Parque Cultural de Valparaíso",
    city: "Valparaíso",
  }),
  semantics: { source_category: { id: "teatro", label: "Teatro y danza" } },
  editorial: {
    merged_category_evidence: [
      { category_id: "teatro", confidence: "high", score: 230, event_id: "a", source_id: "pcdv" },
      { category_id: "teatro", confidence: "low", score: 40, event_id: "b", source_id: "portaltickets_valparaiso" },
    ],
  },
}, "teatro");

console.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");
