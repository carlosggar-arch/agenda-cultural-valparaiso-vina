import { mergeSupplementalPayload } from "./supplemental-events-fetch.js?v=20260819-pipeline1";
import { normalizeAgendaPublicText } from "./public-text-sanitizer.mjs?v=20260820-text1";
import { applyEventDataCorrections } from "./event-data-corrections.js?v=20260819-pipeline1";
import { normalizeAgendaCategories } from "./category-normalizer.js?v=20260819-pipeline1";
import { normalizeAgendaTitles } from "./title-normalizer-bootstrap.js?v=20260820-pipeline2";
import { normalizeSessionOccurrences } from "./session-occurrence-normalizer.js?v=20260819-pipeline1";
import { normalizeFormationCycles } from "./formation-cycle-classifier.js?v=20260820-cycle1";
import { correctArtequinNaturalArtSessions } from "./artequin-session-correction.js?v=20260820-artequin1";
import { deduplicateCrossSourceDataset } from "./cross-source-deduplication.mjs?v=20260819-dedupe1";
import { removeExpiredDatedEvents } from "./runtime-past-event-guard.mjs?v=20260820-pastguard2";
import { applyProgramVisibilityPolicy } from "./program-visibility-policy.js?v=20260819-pipeline1";
import { publishAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";

const LOS_FANTASMAS_EVENT_ID = "agenda_bc147abef119a17edb8a9770";

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

function applyKnownPublicationCategories(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    if (String(event?.id || "") !== LOS_FANTASMAS_EVENT_ID) return event;
    const categories = Array.isArray(event.categories) ? event.categories : [];
    if (categories.some((category) => category?.id === "teatro")) return event;
    changed = true;
    return {
      ...event,
      categories: [...categories, { id: "teatro", label: "Teatro" }],
    };
  });
  return changed ? { ...dataset, events } : dataset;
}

export async function loadAgendaDataset(city, { fetchImpl = globalThis.fetch, now = new Date() } = {}) {
  if (!city?.dataset) throw new Error("Ciudad sin dataset configurado");
  if (typeof fetchImpl !== "function") throw new Error("fetch no disponible");

  const diagnostics = [];
  let dataset = await fetchJson(city.dataset, fetchImpl);
  diagnostics.push({ name: "base", status: "ok" });

  dataset = await withSupplemental(city, dataset, fetchImpl, diagnostics);
  // Structural ingress boundary: no scraped/source HTML is allowed beyond this
  // point. Every later normalizer and every renderer works with plain public text.
  dataset = applyStage("public-text-sanitizer", normalizeAgendaPublicText, dataset, diagnostics);
  if (city.id === "valparaiso") {
    dataset = applyStage("event-data-corrections", applyEventDataCorrections, dataset, diagnostics);
  } else {
    diagnostics.push({ name: "event-data-corrections", status: "not-applicable" });
  }
  dataset = applyStage("category-normalizer", normalizeAgendaCategories, dataset, diagnostics);
  if (city.id === "valparaiso") {
    dataset = applyStage("known-publication-categories", applyKnownPublicationCategories, dataset, diagnostics);
  } else {
    diagnostics.push({ name: "known-publication-categories", status: "not-applicable" });
  }
  dataset = applyStage("title-normalizer", normalizeAgendaTitles, dataset, diagnostics);
  dataset = applyStage("session-occurrence-normalizer", normalizeSessionOccurrences, dataset, diagnostics);
  dataset = applyStage("formation-cycle-classifier", normalizeFormationCycles, dataset, diagnostics);
  if (city.id === "valparaiso") {
    dataset = applyStage("artequin-session-correction", correctArtequinNaturalArtSessions, dataset, diagnostics);
  } else {
    diagnostics.push({ name: "artequin-session-correction", status: "not-applicable" });
  }
  dataset = applyStage("cross-source-deduplication", deduplicateCrossSourceDataset, dataset, diagnostics);
  dataset = applyStage(
    "past-event-guard",
    (current) => removeExpiredDatedEvents(current, {
      now,
      timeZone: city.timezone || current?.timezone || "UTC",
    }),
    dataset,
    diagnostics,
  );

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
