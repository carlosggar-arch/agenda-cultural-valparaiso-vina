import { mergeSupplementalPayload } from "./supplemental-events-fetch.js?v=20260819-pipeline1";
import { applyEventDataCorrections } from "./event-data-corrections.js?v=20260819-pipeline1";
import { normalizeAgendaCategories } from "./category-normalizer.js?v=20260819-pipeline1";
import { normalizeAgendaTitles } from "./title-normalizer-bootstrap.js?v=20260819-pipeline1";
import { normalizeSessionOccurrences } from "./session-occurrence-normalizer.js?v=20260819-pipeline1";
import { deduplicateCrossSourceDataset } from "./cross-source-deduplication.mjs?v=20260819-dedupe1";
import { applyProgramVisibilityPolicy } from "./program-visibility-policy.js?v=20260819-pipeline1";
import { publishAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";

async function fetchJson(url, fetchImpl) {
  const response = await fetchImpl(url, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
  const payload = await response.json();
  if (!payload || !Array.isArray(payload.events)) throw new Error(`Dataset inválido: ${url}`);
  return payload;
}

function applyStage(name, transform, dataset, diagnostics) {
  try {
    const next = transform(dataset);
    diagnostics.push({ name, status: "ok" });
    return next && Array.isArray(next.events) ? next : dataset;
  } catch (error) {
    diagnostics.push({ name, status: "skipped", error: String(error?.message || error) });
    console.warn(`¡Vivamos!: etapa de datos omitida (${name})`, error);
    return dataset;
  }
}

async function withSupplemental(city, dataset, fetchImpl, diagnostics) {
  const url = String(city?.supplemental_dataset || "").trim();
  if (!url) return dataset;
  try {
    const supplemental = await fetchJson(url, fetchImpl);
    diagnostics.push({ name: "supplemental", status: "ok" });
    return mergeSupplementalPayload(dataset, supplemental);
  } catch (error) {
    diagnostics.push({ name: "supplemental", status: "skipped", error: String(error?.message || error) });
    console.warn("¡Vivamos!: eventos suplementarios no disponibles; continúa el dataset principal", error);
    return dataset;
  }
}

export async function loadAgendaDataset(city, { fetchImpl = globalThis.fetch } = {}) {
  if (!city?.dataset) throw new Error("Ciudad sin dataset configurado");
  if (typeof fetchImpl !== "function") throw new Error("fetch no disponible");

  const diagnostics = [];
  let dataset = await fetchJson(city.dataset, fetchImpl);
  diagnostics.push({ name: "base", status: "ok" });

  dataset = await withSupplemental(city, dataset, fetchImpl, diagnostics);
  if (city.id === "valparaiso") {
    dataset = applyStage("event-data-corrections", applyEventDataCorrections, dataset, diagnostics);
  } else {
    diagnostics.push({ name: "event-data-corrections", status: "not-applicable" });
  }
  dataset = applyStage("category-normalizer", normalizeAgendaCategories, dataset, diagnostics);
  dataset = applyStage("title-normalizer", normalizeAgendaTitles, dataset, diagnostics);
  dataset = applyStage("session-occurrence-normalizer", normalizeSessionOccurrences, dataset, diagnostics);
  dataset = applyStage("cross-source-deduplication", deduplicateCrossSourceDataset, dataset, diagnostics);

  let programResult;
  try {
    programResult = applyProgramVisibilityPolicy(dataset);
    diagnostics.push({ name: "program-visibility-policy", status: "ok" });
  } catch (error) {
    diagnostics.push({ name: "program-visibility-policy", status: "skipped", error: String(error?.message || error) });
    console.warn("¡Vivamos!: política de carteleras omitida; continúa la agenda principal", error);
    programResult = { dataset, secondaryPrograms: [], hiddenPrograms: [] };
  }

  const result = {
    dataset: programResult.dataset,
    secondaryPrograms: programResult.secondaryPrograms || [],
    hiddenPrograms: programResult.hiddenPrograms || [],
    diagnostics,
  };
  publishAgendaRuntimeSnapshot(city, result);
  return result;
}
