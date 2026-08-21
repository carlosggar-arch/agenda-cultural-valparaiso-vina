import test from "node:test";
import assert from "node:assert/strict";
import {
  areProbableDuplicateEvents,
  deduplicateCrossSourceDataset,
} from "./cross-source-deduplication.mjs";

function event({
  id,
  title,
  sourceId,
  sourceName,
  official = false,
  start = "2026-08-28T19:00:00-04:00",
  venue = "Parque Cultural de Valparaíso",
  city = "Valparaíso",
  price = { is_free: false, currency: "CLP", min_amount: 7000, max_amount: 12000, display_text: "$7.000 · $12.000" },
}) {
  return {
    id,
    title,
    event_type: "event",
    source_id: sourceId,
    source_name: sourceName,
    source_url: official ? "https://parquecultural.cl/evento" : "https://www.portaldisc.com/evento/matriarcas",
    primary_category: { id: "teatro", label: "Teatro" },
    categories: [{ id: "teatro", label: "Teatro" }],
    schedule: { mode: "dated", start, end: start, occurrences: [{ start, end: start }] },
    location: { venue, city },
    price,
    links: official
      ? { official: "https://parquecultural.cl/events/teatro-matriarcas-poesia-papel-y-tinta/", source: "https://parquecultural.cl/events/teatro-matriarcas-poesia-papel-y-tinta/" }
      : { tickets: "https://www.portaldisc.com/evento/matriarcas-en-parque-cultural-devalparaiso", source: "https://www.portaldisc.com/evento/matriarcas-en-parque-cultural-devalparaiso" },
    public_status: {
      source_official: official,
      information_completeness: "complete",
      price_confirmed: true,
      registration_open: official ? null : true,
    },
    image: official ? { url: "https://parquecultural.cl/matriarcas.jpg" } : { url: "https://portaldisc.com/matriarcas.jpg" },
  };
}

const portal = event({
  id: "portal-matriarcas",
  title: "Matriarcas",
  sourceId: "portaltickets_valparaiso",
  sourceName: "PortalTickets — Región de Valparaíso",
  venue: "Parque Cultural de Valparaíso - Ex Cárcel, Valparaíso",
});
const official = event({
  id: "official-matriarcas",
  title: 'Teatro "Matriarcas: Poesía, Papel y Tinta"',
  sourceId: "parque-cultural",
  sourceName: "Parque Cultural de Valparaíso",
  official: true,
});

test("Matriarcas from ticketing and official sources is one event", () => {
  assert.equal(areProbableDuplicateEvents(portal, official), true);
  const result = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [portal, official] });
  assert.equal(result.events.length, 1);
  assert.equal(result.counts.total, 1);
  assert.equal(result.events[0].id, "official-matriarcas", "official source should be canonical");
  assert.equal(result.events[0].source_name, "Parque Cultural de Valparaíso");
  assert.equal(result.events[0].links.tickets, portal.links.tickets, "ticket link from secondary source should be preserved");
  assert.equal(result.events[0].public_status.registration_open, true, "useful registration status should be preserved");
  assert.deepEqual(new Set(result.events[0].editorial.merged_duplicate_ids), new Set(["portal-matriarcas", "official-matriarcas"]));
});

test("recurring event with a small cross-source time disagreement collapses to the official record", () => {
  const aggregator = event({
    id: "municipal-yoga",
    title: "Yoga y meditación",
    sourceId: "municipal-agenda",
    sourceName: "Agenda municipal",
    start: "2026-08-22T11:00:00-04:00",
    venue: "Jardín Botánico · Viña del Mar",
    city: "Viña del Mar",
    price: { is_free: true, display_text: "Gratis" },
  });
  const venueOfficial = event({
    id: "official-yoga",
    title: "Yoga todos los sábados",
    sourceId: "jardin-botanico",
    sourceName: "Jardín Botánico Nacional de Viña del Mar",
    official: true,
    start: "2026-08-22T10:30:00-04:00",
    venue: "Jardín Botánico Nacional de Viña del Mar",
    city: "Viña del Mar",
    price: { is_free: false, display_text: "Actividad gratuita; se paga entrada al parque" },
  });

  assert.equal(areProbableDuplicateEvents(aggregator, venueOfficial), true);
  const result = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [aggregator, venueOfficial] });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].id, "official-yoga");
  assert.equal(result.events[0].source_name, "Jardín Botánico Nacional de Viña del Mar");
  assert.equal(result.events[0].schedule.start, "2026-08-22T10:30:00-04:00", "official schedule should win the conflict");
  assert.equal(result.events[0].price.is_free, false, "secondary free flag must not overwrite authoritative conditional pricing");
  assert.equal(result.events[0].price.display_text, "Actividad gratuita; se paga entrada al parque");
  assert.equal(result.events[0].editorial.schedule_conflict_resolved, true);
  assert.equal(result.events[0].editorial.deduplication_rule, "same_date_similar_venue_recurring_title_authoritative_source");
});

test("nearby sessions with only a generic title token stay separate without recurrence wording", () => {
  const adults = event({
    id: "yoga-adults",
    title: "Yoga adultos",
    sourceId: "venue",
    sourceName: "Recinto oficial",
    official: true,
    start: "2026-08-22T10:30:00-04:00",
    venue: "Jardín Botánico Nacional de Viña del Mar",
    city: "Viña del Mar",
  });
  const children = event({
    id: "yoga-children",
    title: "Yoga infantil",
    sourceId: "aggregator",
    sourceName: "Agenda externa",
    start: "2026-08-22T11:00:00-04:00",
    venue: "Jardín Botánico · Viña del Mar",
    city: "Viña del Mar",
  });
  assert.equal(areProbableDuplicateEvents(adults, children), false);
});

test("same venue and time with unrelated titles stays separate", () => {
  const other = event({ id: "other", title: "Concierto de cámara", sourceId: "other", sourceName: "Otra fuente" });
  assert.equal(areProbableDuplicateEvents(portal, other), false);
});

test("similar titles at different times stay separate", () => {
  const later = event({
    id: "later",
    title: 'Teatro "Matriarcas: Poesía, Papel y Tinta"',
    sourceId: "other",
    sourceName: "Otra fuente",
    start: "2026-08-28T21:00:00-04:00",
  });
  assert.equal(areProbableDuplicateEvents(portal, later), false);
});

test("similar titles at different venues stay separate", () => {
  const elsewhere = event({
    id: "elsewhere",
    title: 'Teatro "Matriarcas: Poesía, Papel y Tinta"',
    sourceId: "other",
    sourceName: "Otra fuente",
    venue: "Teatro Municipal de Valparaíso",
  });
  assert.equal(areProbableDuplicateEvents(portal, elsewhere), false);
});

test("same source is not collapsed by the cross-source rule", () => {
  const repeated = { ...portal, id: "portal-repeat" };
  assert.equal(areProbableDuplicateEvents(portal, repeated), false);
});
