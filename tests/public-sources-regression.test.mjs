import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { sourceDisplayName } from "../assets/fuentes.js";
import {
  SOURCE_PRIORITY,
  applyCanonicalSourceEvidence,
  classifySourceEvidence,
  chooseCanonicalSourceEvidence,
} from "../app/source-evidence-policy.mjs";
import { deduplicateCrossSourceDataset } from "../app/cross-source-deduplication.mjs";
import { normalizeAgendaSourceEvidence } from "../app/source-evidence-normalizer.mjs";

const catalogue = JSON.parse(
  await readFile(new URL("../fuentes_publicas.json", import.meta.url), "utf8"),
);

const PROTECTED_BASELINE = [
  "Casa de la Cultura de Valparaíso",
  "Del Barrio Valpo",
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
  "Teatro Desastre",
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
  return String(value ?? "").trim().replace(/\/$/, "").toLocaleLowerCase("es");
}

function evidenceEvent({ id, sourceId, sourceName, sourceUrl, official = false, venue = "Teatro Principal", city = "Gijón" }) {
  const start = "2026-08-28T19:00:00+02:00";
  return {
    id,
    title: "Noche de jazz",
    event_type: "event",
    source_id: sourceId,
    source_name: sourceName,
    source_url: sourceUrl,
    primary_category: { id: "musica", label: "Música" },
    categories: [{ id: "musica", label: "Música" }],
    schedule: { mode: "dated", start, end: start, occurrences: [{ start, end: start }] },
    location: { venue, city },
    links: { source: sourceUrl },
    public_status: { source_official: official, information_completeness: "complete" },
  };
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
  assert.deepEqual(missing, [], `previously integrated public sources disappeared: ${missing.join(", ")}`);
});

test("Visita Viña has a clear public display name without changing its stable source id", () => {
  const source = catalogue.sources.find((item) => item.canonical_source_id === "culturasvina");
  assert.ok(source, "the existing culturasvina source must remain registered");
  assert.equal(sourceDisplayName(source), "Visita Viña — Municipalidad de Viña del Mar");
  assert.equal(source.canonical_source_id, "culturasvina");
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
    assert.ok(source.cities.every((city) => city === "Valparaíso" || city === "Viña del Mar"), `${source.name} contains an out-of-scope city`);
  }
});

test("priority source expansion is present and BAJ remains single", () => {
  assert.ok(
    catalogue.sources.length >= PROTECTED_BASELINE.length,
    "source catalogue may grow but must not shrink below the protected baseline",
  );
  const names = catalogue.sources.map((source) => source.name);
  assert.equal(names.filter((name) => name === "Balmaceda Arte Joven Valparaíso").length, 1);
  for (const name of [
    "Teatro Municipal de Valparaíso",
    "Casa de la Cultura de Valparaíso",
    "Estrella Negra Club de Jazz",
    "Casa Prisma Valpo",
    "Estadio Español Recreo",
    "El Pasaje Café Viña",
    "Teatro Desastre",
    "Del Barrio Valpo",
  ]) assert.ok(names.includes(name), `${name} must remain integrated`);
});

test("Teatro Desastre remains an organizer source", () => {
  const source = catalogue.sources.find((item) => item.name === "Teatro Desastre");
  assert.ok(source);
  assert.equal(source.website_url, "https://www.instagram.com/desastreteatro/");
  assert.deepEqual(source.cities, ["Valparaíso"]);
  assert.equal(source.source_type, "Organización cultural");
  assert.deepEqual(source.categories, ["Teatro"]);
});

test("Del Barrio Valpo remains a filtered local venue source", () => {
  const source = catalogue.sources.find((item) => item.name === "Del Barrio Valpo");
  assert.ok(source);
  assert.equal(source.website_url, "https://www.instagram.com/delbarriovalpo/");
  assert.deepEqual(source.cities, ["Valparaíso"]);
  assert.equal(source.source_type, "Centro cultural");
  assert.deepEqual(source.categories, ["Música", "Ferias y gastronomía"]);
});

test("El Pasaje Café Viña remains a local integrated source", () => {
  const source = catalogue.sources.find((item) => item.name === "El Pasaje Café Viña");
  assert.ok(source);
  assert.equal(source.website_url, "https://elpasaje.cl/");
  assert.deepEqual(source.cities, ["Viña del Mar"]);
  assert.deepEqual(source.categories, ["Música", "Ferias y gastronomía"]);
  assert.equal(source.public_status, "integrada");
});

test("Valparaíso Profundo remains a first-class integrated source", () => {
  const source = catalogue.sources.find((item) => item.name === "Valparaíso Profundo");
  assert.ok(source);
  assert.equal(source.website_url, "https://valparaisoprofundo.cl/");
  assert.deepEqual(source.cities, ["Valparaíso"]);
  assert.equal(source.public_status, "integrada");
});

test("event source hierarchy is explicit and stable", () => {
  assert.deepEqual(SOURCE_PRIORITY, {
    official: 0,
    institutional: 1,
    ticketing: 2,
    web: 3,
    social_aggregator: 4,
  });

  const official = evidenceEvent({
    id: "official",
    sourceId: "teatro",
    sourceName: "Teatro Principal",
    sourceUrl: "https://teatro.example/evento",
    official: true,
  });
  const institutional = evidenceEvent({ id: "institutional", sourceId: "gijon", sourceName: "Ayuntamiento de Gijón", sourceUrl: "https://www.gijon.es/evento" });
  const ticketing = evidenceEvent({ id: "tickets", sourceId: "passline", sourceName: "Passline", sourceUrl: "https://www.passline.com/evento" });
  const web = evidenceEvent({ id: "web", sourceId: "cultura", sourceName: "Cultura local", sourceUrl: "https://culturalocal.example/evento" });
  const social = evidenceEvent({ id: "social", sourceId: "instagram", sourceName: "Instagram", sourceUrl: "https://www.instagram.com/p/ABC/?igsh=tracking" });

  assert.equal(classifySourceEvidence(official, official.source_url).source_kind, "official");
  assert.equal(classifySourceEvidence(institutional, institutional.source_url).source_kind, "institutional");
  assert.equal(classifySourceEvidence(ticketing, ticketing.source_url).source_kind, "ticketing");
  assert.equal(classifySourceEvidence(web, web.source_url).source_kind, "web");
  assert.equal(classifySourceEvidence(social, social.source_url).source_kind, "social_aggregator");

  const evidence = chooseCanonicalSourceEvidence(social, web, ticketing, institutional, official);
  assert.equal(evidence.primary.url, "https://teatro.example/evento");
  assert.deepEqual(evidence.secondary.map((item) => item.source_kind), [
    "institutional", "ticketing", "web", "social_aggregator",
  ]);
});

test("event source canonicalization is idempotent and aligns links.source", () => {
  const ticketing = evidenceEvent({ id: "tickets", sourceId: "passline", sourceName: "Passline", sourceUrl: "https://www.passline.com/evento" });
  ticketing.links.tickets = ticketing.source_url;
  const official = evidenceEvent({
    id: "official",
    sourceId: "teatro",
    sourceName: "Teatro Principal",
    sourceUrl: "https://teatro.example/evento",
    official: true,
  });
  official.links.official = official.source_url;

  const merged = applyCanonicalSourceEvidence(ticketing, official);
  assert.equal(merged.source_url, "https://teatro.example/evento");
  assert.deepEqual(merged.secondary_source_urls, ["https://passline.com/evento"]);
  assert.equal(merged.links.source, merged.source_url);
  assert.deepEqual(applyCanonicalSourceEvidence(merged, official), merged);
});

test("cross-source duplicate becomes explicit secondary evidence", () => {
  const institutional = evidenceEvent({
    id: "municipal-jazz",
    sourceId: "gijon-agenda",
    sourceName: "Ayuntamiento de Gijón",
    sourceUrl: "https://www.gijon.es/evento/jazz",
  });
  const ticketing = evidenceEvent({
    id: "ticket-jazz",
    sourceId: "ticketmaster",
    sourceName: "Ticketmaster",
    sourceUrl: "https://www.ticketmaster.es/event/jazz",
  });
  ticketing.links.tickets = ticketing.source_url;

  const deduped = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [ticketing, institutional] });
  assert.equal(deduped.events.length, 1);
  assert.equal(deduped.events[0].editorial.cross_source_deduplicated, true);

  const normalized = normalizeAgendaSourceEvidence(deduped);
  assert.equal(normalized.events[0].source_url, "https://gijon.es/evento/jazz");
  assert.deepEqual(normalized.events[0].secondary_source_urls, ["https://ticketmaster.es/event/jazz"]);
  assert.equal(normalized.events[0].links.tickets, "https://www.ticketmaster.es/event/jazz");
});

test("explicit official link outranks institutional and ticketing evidence", () => {
  const event = evidenceEvent({
    id: "mixed",
    sourceId: "ticketmaster",
    sourceName: "Ticketmaster",
    sourceUrl: "https://ticketmaster.es/event/x",
  });
  event.links = {
    source: event.source_url,
    tickets: event.source_url,
    official: "https://teatroprincipal.example/programacion/x",
  };
  event.secondary_source_urls = ["https://www.gijon.es/evento/x"];

  const normalized = applyCanonicalSourceEvidence(event);
  assert.equal(normalized.source_url, "https://teatroprincipal.example/programacion/x");
  assert.deepEqual(normalized.secondary_source_urls, [
    "https://gijon.es/evento/x",
    "https://ticketmaster.es/event/x",
  ]);
});
