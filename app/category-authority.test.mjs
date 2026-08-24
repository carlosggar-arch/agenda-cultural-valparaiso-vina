import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  canonicalPublicCategory,
  classifyPublicCategory,
  resolvePublicCategory,
} from "./public-category-rules.mjs";

const taxonomy = JSON.parse(
  readFileSync(new URL("../shared/public-category-taxonomy.json", import.meta.url), "utf8"),
);
const core = readFileSync(new URL("./app-core.js", import.meta.url), "utf8");
const combined = readFileSync(new URL("./combined-filters.js", import.meta.url), "utf8");

assert.equal(taxonomy.schema_version, "2.3.0");
assert.equal(taxonomy.fallback_category, "unclassified");
assert.equal(taxonomy.categories.unclassified.thematic, false);
assert.equal(taxonomy.categories.unclassified.label, "Otros panoramas");

const expectedLabels = {
  musica: "Música",
  teatro: "Teatro y danza",
  cine: "Cine",
  exposiciones: "Exposiciones",
  "charlas-conferencias": "Charlas y conferencias",
  literatura: "Literatura",
  "cursos-talleres-campus": "Cursos, talleres y experiencias",
  "deportes-actividad-fisica": "Deportes y actividad física",
  "naturaleza-aire-libre": "Naturaleza y aire libre",
  "ferias-vida-local": "Ferias y vida local",
  unclassified: "Otros panoramas",
};
for (const [id, label] of Object.entries(expectedLabels)) {
  assert.equal(taxonomy.categories[id]?.label, label, `${id} label must be shared`);
}

const expectedAliases = {
  museos: "exposiciones",
  "artes-visuales-museo": "exposiciones",
  "cursos-talleres": "cursos-talleres-campus",
  deportes: "deportes-actividad-fisica",
  charlas: "charlas-conferencias",
  "literatura-charlas-encuentros": "unclassified",
  "naturaleza-montana": "naturaleza-aire-libre",
  gastronomia: "ferias-vida-local",
  "teatro-artes-escenicas": "teatro",
  otros: "unclassified",
  "actividad-panorama": "unclassified",
  "naturaleza-deportes": "unclassified",
};
for (const [alias, canonical] of Object.entries(expectedAliases)) {
  assert.equal(taxonomy.aliases[alias], canonical, `${alias} alias must live in shared taxonomy`);
  assert.equal(
    canonicalPublicCategory({ id: alias, label: alias })?.id,
    canonical,
    `${alias} must resolve through shared taxonomy`,
  );
}

const cases = [
  [
    "music fallback recovery",
    { title: "Concierto de cámara al atardecer", primary_category: { id: "otros", label: "Otros panoramas" } },
    "musica",
  ],
  [
    "theatre fallback recovery",
    { title: "Obra de teatro La memoria del agua", primary_category: { id: "otros", label: "Otros panoramas" } },
    "teatro",
  ],
  [
    "sports fallback recovery",
    { title: "Torneo abierto de tenis", primary_category: { id: "otros", label: "Otros panoramas" } },
    "deportes-actividad-fisica",
  ],
  [
    "literature now has a semantic home",
    { title: "Presentación del libro Decadencia", primary_category: { id: "otros", label: "Otros panoramas" } },
    "literatura",
  ],
  [
    "reading club is literature, not training",
    { title: "Club de Lectura para la Niñez | Caleta de Historias", primary_category: { id: "otros", label: "Otros panoramas" } },
    "literatura",
  ],
  [
    "nature outing",
    { title: "Salida de senderismo por la costa", primary_category: { id: "naturaleza-deportes", label: "Naturaleza y deportes" } },
    "naturaleza-aire-libre",
  ],
  [
    "local fair",
    { title: "Feria de productores y oficios del barrio", primary_category: { id: "otros", label: "Otros panoramas" } },
    "ferias-vida-local",
  ],
  [
    "bioparc educational encounter becomes experience",
    {
      title: "Encuentro Educativo Tiburones",
      source_id: "bioparc_acuario_gijon",
      source_name: "BIOPARC Acuario de Gijón — Actividades y talleres",
      primary_category: { id: "actividad-panorama", label: "Actividad / panorama" },
    },
    "cursos-talleres-campus",
  ],
  [
    "bioparc generic activity uses source evidence",
    {
      title: "Alimentación del Gran Oceanario",
      source_id: "bioparc_acuario_gijon",
      source_name: "BIOPARC Acuario de Gijón — Actividades y talleres",
      primary_category: { id: "actividad-panorama", label: "Actividad / panorama" },
    },
    "cursos-talleres-campus",
  ],
  [
    "bioparc concert remains music",
    {
      title: "Concierto piano a la luz de las velas",
      source_id: "bioparc_acuario_gijon",
      source_name: "BIOPARC Acuario de Gijón — Actividades y talleres",
      primary_category: { id: "actividad-panorama", label: "Actividad / panorama" },
    },
    "musica",
  ],
  [
    "camera Dire Straits tribute is music",
    {
      title: "HOMENAJE DIRE STRAITS",
      source_id: "camara_recinto_ferial_gijon",
      primary_category: { id: "actividad-panorama", label: "Actividad / panorama" },
    },
    "musica",
  ],
  [
    "camera Gran Showman is stage musical",
    {
      title: "EL GRAN SHOWMAN",
      source_id: "camara_recinto_ferial_gijon",
      primary_category: { id: "actividad-panorama", label: "Actividad / panorama" },
    },
    "teatro",
  ],
  [
    "generic musical is theatre",
    { title: "La Bella y la Bestia, el musical", primary_category: { id: "actividad-panorama", label: "Actividad / panorama" } },
    "teatro",
  ],
  [
    "ambiguous remains unclassified",
    { title: "Encuentro de agosto", description: "Actividad abierta a la comunidad.", primary_category: { id: "otros", label: "Otros panoramas" } },
    "unclassified",
  ],
];

for (const [name, event, expected] of cases) {
  assert.equal(resolvePublicCategory(event).id, expected, name);
}

// A strong title signal beats a conflicting source bucket.
assert.equal(
  resolvePublicCategory({
    title: "Concierto sinfónico de invierno",
    primary_category: { id: "teatro", label: "Teatro" },
  }).id,
  "musica",
);

// A trusted thematic source category is not displaced by weak description-only language.
assert.equal(
  resolvePublicCategory({
    title: "La casa azul",
    description: "Obra teatral con música en vivo.",
    primary_category: { id: "teatro", label: "Teatro" },
  }).id,
  "teatro",
);

// Generic venue/source-name words still do not create a category by themselves.
assert.equal(
  resolvePublicCategory({
    title: "Encuentro de agosto",
    source_name: "Teatro Municipal de Prueba",
    primary_category: { id: "otros", label: "Otros panoramas" },
  }).id,
  "unclassified",
);

// Lifecycle must never decide the thematic category.
assert.equal(
  resolvePublicCategory({
    title: "Inscripciones abiertas",
    event_type: "registration_period",
    description: "Inscripción para torneo de ciclismo.",
    primary_category: { id: "otros", label: "Otros panoramas" },
  }).id,
  "deportes-actividad-fisica",
);

// Classification is explainable and keeps provenance without turning it into authority.
const explained = classifyPublicCategory({
  title: "Concierto de jazz",
  primary_category: { id: "otros", label: "Otros panoramas" },
});
assert.equal(explained.category.id, "musica");
assert.equal(explained.confidence, "high");
assert.ok(explained.evidence.some((item) => item.kind === "title"));
assert.equal(explained.source_category.id, "otros");

for (const [name, source] of [["app-core", core], ["combined-filters", combined]]) {
  assert.match(source, /canonicalPublicCategory/, `${name} must consume the shared category authority`);
  assert.doesNotMatch(source, /MUSEUM_CATEGORY_ID/, `${name} must not declare a museum alias constant`);
  assert.doesNotMatch(source, /id\s*===\s*["']museos["']/, `${name} must not implement museos remapping`);
  assert.doesNotMatch(source, /id\s*=\s*["']exposiciones["']/, `${name} must not assign canonical categories locally`);
}

console.log("SINGLE_PUBLIC_CATEGORY_AUTHORITY_OK");
