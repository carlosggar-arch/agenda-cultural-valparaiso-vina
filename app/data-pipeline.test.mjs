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

console.log("DATA_PIPELINE_OK");
