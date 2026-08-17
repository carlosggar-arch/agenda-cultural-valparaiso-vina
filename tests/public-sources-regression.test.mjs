import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const catalogue = JSON.parse(
  await readFile(new URL("../fuentes_publicas.json", import.meta.url), "utf8"),
);

const PROTECTED_BASELINE = [
  "Casa de la Cultura de Valparaíso",
  "Estadio Español Recreo",
  "Estrella Negra Club de Jazz",
  "El Pasaje Café Viña",
  "Masita Rica",
  "Trotamundos Valparaíso",
  "Valparaíso Profundo",
  "La Escala Galería",
  "Culturas Viña",
  "Teatro Municipal de Valparaíso",
  "Teatro Municipal de Viña del Mar",
  "Valpo Cultura",
  "Artequin Viña del Mar",
  "CENTEX",
  "Museo Baburizza",
  "Museo de Historia Natural de Valparaíso",
  "Museo Fonck",
  "Museo Palacio Rioja",
  "CONAF — Reserva Nacional Lago Peñuelas",
  "Casa Prisma Valpo",
  "Compañía La Paila",
  "EcoLiderazgo",
  "Itaú Maratón de Viña — sitio oficial",
  "Balmaceda Arte Joven Valparaíso",
  "Centro de Extensión Duoc UC Valparaíso",
  "Cine Arte Viña del Mar",
  "Cultura PUCV",
  "Cultura USM",
  "Insomnia Cine",
  "Parque Cultural de Valparaíso",
  "Sala Secreta",
  "Sala Teatro IPA",
  "Teatro La Peste",
  "Teatro Mauri SCD",
  "TeatroMuseo",
];

function normalizedUrl(value) {
  return String(value ?? "")
    .trim()
    .replace(/\/$/, "")
    .toLocaleLowerCase("es");
}

test("public sources catalogue preserves the integrated baseline", () => {
  assert.equal(catalogue.schema_version, "1.0.0");
  assert.ok(Array.isArray(catalogue.sources), "sources must be an array");
  assert.ok(
    catalogue.sources.length >= PROTECTED_BASELINE.length,
    `expected at least ${PROTECTED_BASELINE.length} integrated sources, got ${catalogue.sources.length}`,
  );

  const names = new Set(catalogue.sources.map((source) => source.name));
  const missing = PROTECTED_BASELINE.filter((name) => !names.has(name));
  assert.deepEqual(
    missing,
    [],
    `previously integrated public sources disappeared: ${missing.join(", ")}`,
  );
});

test("public sources catalogue has stable unique public records", () => {
  const ids = catalogue.sources.map((source) => source.id);
  assert.equal(new Set(ids).size, ids.length, "duplicate public source ids detected");

  const urls = catalogue.sources.map((source) => normalizedUrl(source.website_url));
  assert.ok(urls.every(Boolean), "every public source must have a usable public URL");
  assert.equal(new Set(urls).size, urls.length, "duplicate public source URLs detected");

  for (const source of catalogue.sources) {
    assert.equal(source.public_status, "integrada");
    assert.ok(Array.isArray(source.cities) && source.cities.length > 0);
    assert.ok(
      source.cities.every((city) => city === "Valparaíso" || city === "Viña del Mar"),
      `${source.name} contains an out-of-scope city`,
    );
  }
});

test("priority source expansion is present and BAJ remains single", () => {
  assert.equal(catalogue.sources.length, 35);
  const names = catalogue.sources.map((source) => source.name);
  assert.equal(names.filter((name) => name === "Balmaceda Arte Joven Valparaíso").length, 1);

  for (const name of [
    "Teatro Municipal de Valparaíso",
    "Casa de la Cultura de Valparaíso",
    "Estrella Negra Club de Jazz",
    "Casa Prisma Valpo",
    "Estadio Español Recreo",
    "El Pasaje Café Viña",
  ]) {
    assert.ok(names.includes(name), `${name} must remain integrated`);
  }
});

test("El Pasaje Café Viña remains a local integrated source", () => {
  const source = catalogue.sources.find((item) => item.name === "El Pasaje Café Viña");
  assert.ok(source, "El Pasaje Café Viña must remain in the public source catalogue");
  assert.equal(source.website_url, "https://elpasaje.cl/");
  assert.deepEqual(source.cities, ["Viña del Mar"]);
  assert.deepEqual(source.categories, ["Música", "Ferias y gastronomía"]);
  assert.equal(source.public_status, "integrada");
});

test("Valparaíso Profundo remains a first-class integrated source", () => {
  const source = catalogue.sources.find((item) => item.name === "Valparaíso Profundo");
  assert.ok(source, "Valparaíso Profundo must remain in the public source catalogue");
  assert.equal(source.website_url, "https://valparaisoprofundo.cl/");
  assert.deepEqual(source.cities, ["Valparaíso"]);
  assert.equal(source.public_status, "integrada");
});
