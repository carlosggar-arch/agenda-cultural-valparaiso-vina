import test from "node:test";
import assert from "node:assert/strict";
import {
  areProbableDuplicateEvents,
  deduplicateCrossSourceDataset,
  venuesLikelySame,
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

test("direct venue source resolves a recurring schedule conflict even when upstream marks it non-official", () => {
  const aggregator = event({
    id: "visitavina-yoga",
    title: "Yoga y meditación",
    sourceId: "culturasvina",
    sourceName: "Visita Viña — Municipalidad de Viña del Mar",
    start: "2026-08-22T11:00:00-04:00",
    venue: "Jardín Botánico",
    city: "Viña del Mar",
    price: { is_free: true, display_text: "Gratis" },
  });
  aggregator.source_url = "https://visitavina.munivina.cl/actividad/yoga-y-meditacion-7/";
  aggregator.links = {
    official: "https://visitavina.munivina.cl/actividad/yoga-y-meditacion-7/",
    source: "https://visitavina.munivina.cl/actividad/yoga-y-meditacion-7/",
  };

  const directVenue = event({
    id: "jbn-yoga",
    title: "Yoga todos los sábados",
    sourceId: "jbn",
    sourceName: "Jardín Botánico Nacional de Viña del Mar",
    start: "2026-08-22T10:30:00-04:00",
    venue: "Jardín Botánico Nacional de Viña del Mar",
    city: "Viña del Mar",
    price: { is_free: false, display_text: "Actividad gratuita; se paga entrada al parque" },
  });
  directVenue.source_url = "https://jbn.cl/calendario-actividades/";
  directVenue.links = {
    official: "https://jbn.cl/calendario-actividades/",
    source: "https://jbn.cl/calendario-actividades/",
  };
  directVenue.public_status.source_official = false;

  assert.equal(areProbableDuplicateEvents(aggregator, directVenue), true);
  const result = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [aggregator, directVenue] });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].id, "jbn-yoga", "direct venue source should become canonical despite the bad upstream flag");
  assert.equal(result.events[0].source_name, "Jardín Botánico Nacional de Viña del Mar");
  assert.equal(result.events[0].schedule.start, "2026-08-22T10:30:00-04:00");
  assert.equal(result.events[0].price.is_free, false);
  assert.equal(result.events[0].price.display_text, "Actividad gratuita; se paga entrada al parque");
});

test("same provider website and social records reconcile to the stronger event evidence", () => {
  const web = event({
    id: "caleta-web",
    title: "Club de lectura para la niñez | Caleta de Historias",
    sourceId: "valpocultura",
    sourceName: "Valpo Cultura",
    official: true,
    start: "2026-08-22T12:00:00-04:00",
    venue: "Biblioteca Municipal de Playa Ancha",
    city: "Valparaíso",
    price: { is_free: null, display_text: null },
  });
  web.source_url = "https://valpocultura.cl/evento/biblioteca-de-playa-ancha-caleta-de-historias/";
  web.links = {
    official: web.source_url,
    source: web.source_url,
    registration: null,
  };
  web.schedule = {
    mode: "multi_day",
    start: "2026-08-22T12:00:00-04:00",
    end: "2026-08-22T13:30:00-04:00",
    display_text: "22-08-2026 · 12:00–13:30",
    occurrences: [],
  };
  web.public_status = {
    source_official: true,
    information_completeness: "complete",
    price_confirmed: true,
    registration_open: null,
  };
  web.image = { url: "https://valpocultura.cl/wp-content/uploads/2026/08/caleta.png" };

  const social = event({
    id: "caleta-social",
    title: "CLUB DE LECTURA PARA LA NIÑEZ | CALETA DE HISTORIAS",
    sourceId: "valpocultura",
    sourceName: "Valpo Cultura",
    start: "2026-08-22T12:00:00-04:00",
    venue: "Biblioteca Municipal de Playa Ancha",
    city: "Valparaíso",
    price: { is_free: null, display_text: null },
  });
  social.source_url = "https://www.instagram.com/p/caleta-social/";
  social.links = { official: social.source_url, source: social.source_url, registration: null };
  social.schedule = {
    mode: "multi_day",
    start: "2026-08-22T12:00:00-04:00",
    end: "2026-11-22",
    display_text: "2026-08-22 · 12:00",
    occurrences: [],
  };
  social.public_status = {
    source_official: true,
    information_completeness: "partial",
    price_confirmed: null,
    registration_open: null,
  };
  social.tags = ["cupos", "inscripciones"];

  assert.equal(areProbableDuplicateEvents(web, social), true, "distinct records from one provider must still reconcile");
  const result = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [social, web] });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].id, "caleta-web", "the complete official event page must win over the social scrape");
  assert.equal(result.events[0].schedule.end, "2026-08-22T13:30:00-04:00", "authoritative event duration must survive reconciliation");
  assert.equal(result.events[0].image.url, web.image.url, "specific website event image must survive reconciliation");
  assert.equal(result.events[0].editorial.same_provider_reconciled, true);
  assert.equal(result.events[0].editorial.deduplication_rule, "same_provider_distinct_record_duplicate");
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

test("exact repeat of the same source record is not collapsed by the reconciliation rule", () => {
  const repeated = { ...portal, id: "portal-repeat" };
  assert.equal(areProbableDuplicateEvents(portal, repeated), false);
});


test("Gijon recovered social caption reconciles with official installation record", () => {
  const social = event({
    id: "gijon-social-capsula",
    title: "Cápsula Radio: La tercera luz",
    sourceId: "agenda_gijon",
    sourceName: "Agenda Gijón",
    start: "2026-08-03T06:00:00+02:00",
    venue: "Primera planta del Antiguo Instituto Jovellanos",
    city: "Gijón",
  });
  social.schedule.end = "2026-08-30";
  social.primary_category = { id: "teatro", label: "Teatro y danza" };
  social.categories = [{ id: "teatro", label: "Teatro y danza" }];
  social.description = "Cápsula Radio: La tercera luz. Instalación de ficción sonora, radiocápsula y teatro de objetos.";
  social.public_status.source_official = false;
  social.source_url = "https://www.instagram.com/p/agenda-gijon-capsula/";
  social.links = { source: social.source_url };

  const official = event({
    id: "gijon-official-capsula",
    title: 'Instalación. Ficción sonora. CÁPSULA RADIO: "La tercera Luz"',
    sourceId: "gijon_opendata_events",
    sourceName: "Ayuntamiento de Gijón — Agenda",
    official: true,
    start: "2026-08-04",
    venue: "Centro de Cultura Antiguo Instituto",
    city: "Gijón",
  });
  official.schedule.end = "2026-08-30";
  official.primary_category = { id: "exposiciones", label: "Exposiciones" };
  official.categories = [{ id: "exposiciones", label: "Exposiciones" }];
  official.semantics = { source_category: { id: "exposiciones", label: "Exposiciones" }, primary_domain: "exposiciones", confidence: "high", score: 120 };
  official.source_url = "https://www.gijon.es/es/eventos/instalacion-ficcion-sonora-capsula-radio-la-tercera-luz";
  official.links = { official: official.source_url, source: official.source_url };

  assert.equal(venuesLikelySame(social, official), true, "building-floor wording must not split one venue");
  assert.equal(areProbableDuplicateEvents(social, official), true, "recovered work identity plus venue/date must reconcile");
  const result = deduplicateCrossSourceDataset({ counts: { total: 2, events: 2 }, events: [social, official] });
  assert.equal(result.events.length, 1);
  assert.equal(result.events[0].id, "gijon-official-capsula", "official municipal record must be canonical");
  assert.equal(result.events[0].primary_category.id, "exposiciones");
  assert.match(result.events[0].title, /CÁPSULA RADIO/i);
});
