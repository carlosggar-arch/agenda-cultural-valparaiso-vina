import assert from "node:assert/strict";
import { loadAgendaDataset } from "./data-pipeline.js";

function response(payload, ok = true, status = 200) {
  return {
    ok,
    status,
    async json() { return payload; },
  };
}

const baseEvent = {
  id: "event-centex",
  title: "Concierto de prueba",
  event_type: "event",
  source_id: "centex",
  source_name: "CENTEX",
  primary_category: { id: "musica", label: "Música" },
  categories: [{ id: "musica", label: "Música" }],
  schedule: { start: "2026-08-20T19:00:00-04:00", end: null, occurrences: [] },
  location: { venue: "CENTEX", city: "Valparaíso" },
  price: { is_free: true, display_text: "Gratis" },
  links: { official: "https://example.test/concierto" },
};

const program = {
  id: "program-centex",
  title: "Centex – Cartelera Agosto",
  event_type: "program",
  source_id: "valpocultura",
  source_name: "Valpo Cultura",
  organizer: "CENTEX",
  primary_category: { id: "cultura", label: "Cultura" },
  categories: [{ id: "cultura", label: "Cultura" }],
  schedule: { start: "2026-08-01", end: "2026-08-31", occurrences: [] },
  location: { venue: "CENTEX", city: "Valparaíso" },
  price: { is_free: true, display_text: "Gratis" },
  links: { official: "https://example.test/cartelera" },
  editorial: { covered_source_ids: ["centex"] },
};

const supplemental = {
  id: "supplemental-event",
  title: "Actividad suplementaria",
  event_type: "event",
  source_id: "extra",
  source_name: "Extra",
  primary_category: { id: "teatro", label: "Teatro" },
  categories: [{ id: "teatro", label: "Teatro" }],
  schedule: { start: "2026-08-21T20:00:00-04:00", end: null, occurrences: [] },
  location: { venue: "Sala Extra", city: "Valparaíso" },
  price: { is_free: false, display_text: "$5.000" },
  links: { official: "https://example.test/extra" },
};

{
  const requests = [];
  const fetchImpl = async (url) => {
    requests.push(String(url));
    if (String(url) === "base.json") return response({ counts: { total: 2, events: 1, programs: 1 }, events: [baseEvent, program] });
    if (String(url) === "supplemental.json") return response({ events: [supplemental] });
    return response({}, false, 404);
  };
  const result = await loadAgendaDataset({ dataset: "base.json", supplemental_dataset: "supplemental.json" }, { fetchImpl });
  assert.deepEqual(requests, ["base.json", "supplemental.json"]);
  assert.equal(result.dataset.events.some((event) => event.id === "program-centex"), false, "covered programs must leave the primary list");
  assert.equal(result.dataset.events.some((event) => event.id === "supplemental-event"), true, "supplemental events must be merged explicitly");
  assert.equal(result.hiddenPrograms.length, 1);
  assert.equal(result.diagnostics.every((stage) => stage.status === "ok"), true);
}

{
  const fetchImpl = async (url) => {
    if (String(url) === "base.json") return response({ counts: { total: 1, events: 1, programs: 0 }, events: [baseEvent] });
    throw new Error("supplemental unavailable");
  };
  const result = await loadAgendaDataset({ dataset: "base.json", supplemental_dataset: "missing.json" }, { fetchImpl });
  assert.equal(result.dataset.events.some((event) => event.id === "event-centex"), true, "supplemental failure must preserve the base agenda");
  assert.equal(result.diagnostics.find((stage) => stage.name === "supplemental")?.status, "skipped");
}

{
  const cinema = (id, start, venue = "Cine Arte Viña del Mar") => ({
    id,
    title: "Adolescencia, Sexo y Muerte en Camp Miasma",
    event_type: "event",
    source_id: venue === "Cine Arte Viña del Mar" ? "cinearte_vina" : "insomnia_cine",
    source_name: venue === "Cine Arte Viña del Mar" ? "Cine Arte Viña del Mar" : "INSOMNIA Teatro Condell",
    primary_category: { id: "cine", label: "Cine" },
    categories: [{ id: "cine", label: "Cine" }],
    schedule: { mode: "dated", start, end: start, occurrences: [] },
    location: { venue, city: venue === "Cine Arte Viña del Mar" ? "Viña del Mar" : "Valparaíso" },
    price: { is_free: false, currency: "CLP", min_amount: 5500, max_amount: 5500, display_text: "$5.500" },
    links: { tickets: venue === "Cine Arte Viña del Mar" ? "https://passline.test/miasma-vina" : "https://passline.test/miasma-insomnia" },
  });
  const events = [
    cinema("miasma-1300", "2026-08-19T13:00:00-04:00"),
    cinema("miasma-1800", "2026-08-19T18:00:00-04:00"),
    cinema("miasma-insomnia", "2026-08-22T17:45:00-04:00", "INSOMNIA Teatro Condell"),
  ];
  const fetchImpl = async () => response({ counts: { total: 3, events: 3, programs: 0 }, events });
  const result = await loadAgendaDataset({ dataset: "base.json" }, { fetchImpl });
  const cineArte = result.dataset.events.filter((event) => event.title === events[0].title && event.location?.venue === "Cine Arte Viña del Mar");
  assert.equal(cineArte.length, 1, "same-title sessions at Cine Arte Viña must render as one event");
  assert.equal(cineArte[0].schedule?.mode, "multi_session");
  assert.deepEqual(cineArte[0].schedule?.occurrences?.map((item) => item.start), [
    "2026-08-19T13:00:00-04:00",
    "2026-08-19T18:00:00-04:00",
  ]);
  assert.equal(result.dataset.events.some((event) => event.id === "miasma-insomnia"), true, "sessions at a different venue must remain separate");
}

{
  const marDulce = {
    id: "mar-dulce-existing",
    title: "A veces un mar dulce",
    event_type: "event",
    source_id: "museo_palacio_rioja",
    source_name: "Museo Palacio Rioja",
    primary_category: { id: "exposiciones", label: "Exposiciones" },
    categories: [{ id: "exposiciones", label: "Exposiciones" }],
    schedule: { mode: "dated", start: "2026-08-19T06:00:00-04:00", end: "2026-08-19T13:30:00-04:00", occurrences: [] },
    location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" },
    price: { is_free: true, display_text: "Gratis" },
    links: { official: "https://visitavina.munivina.cl/actividad/exposicion-temporal-a-veces-un-mar-dulce/" },
  };
  const fetchImpl = async () => response({ counts: { total: 1, events: 1, programs: 0 }, events: [marDulce] });
  const result = await loadAgendaDataset({ dataset: "base.json" }, { fetchImpl });
  const riojaExhibitions = result.dataset.events.filter((event) =>
    event.primary_category?.id === "exposiciones" && event.location?.venue === "Museo Palacio Rioja"
  );
  const titles = new Set(riojaExhibitions.map((event) => event.title));
  assert.equal(titles.has("A veces un mar dulce"), true);
  assert.equal(titles.has("Muestra temporal // Mis objetos, mi patrimonio"), true, "missing official Rioja exhibition must be recovered");
  assert.equal(titles.has("Visita guiada exposición // “A veces un mar dulce”"), true, "guided exhibition visit must share the museum group");
  const corrected = riojaExhibitions.find((event) => event.id === "mar-dulce-existing");
  assert.equal(corrected.schedule?.mode, "multi_day");
  assert.equal(corrected.schedule?.end, "2026-08-30");
  assert.equal(corrected.schedule?.opening_hours?.display_text, "Martes a domingo · 10:00–17:30");
}

console.log("DATA_PIPELINE_OK");
