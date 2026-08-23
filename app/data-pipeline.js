import { mergeSupplementalPayload } from "./supplemental-events-fetch.js?v=20260819-pipeline1";
import { normalizeAgendaPublicText } from "./public-text-sanitizer.mjs?v=20260820-text1";
import { applyEventDataCorrections } from "./event-data-corrections.js?v=20260819-pipeline1";
import { normalizeAgendaCategories } from "./category-normalizer.js?v=20260821-shared-taxonomy1";
import { normalizeVenueAliases } from "./venue-identity.mjs?v=20260820-venues1";
import { normalizeAgendaTitles, recoverAgendaTitles } from "./title-normalizer-bootstrap.js?v=20260822-title-authority1";
import { normalizeSessionOccurrences } from "./session-occurrence-normalizer.js?v=20260819-pipeline1";
import { normalizeFormationCycles } from "./formation-cycle-classifier.js?v=20260821-shared-taxonomy1";
import { correctArtequinNaturalArtSessions } from "./artequin-session-correction.js?v=20260820-artequin1";
import { deduplicateCrossSourceDataset } from "./cross-source-deduplication.mjs?v=20260819-dedupe1";
import { enrichCitySourceEvidence } from "./city-source-evidence-adapter.mjs?v=20260822-source-authority1";
import { normalizeAgendaSourceEvidence } from "./source-evidence-normalizer.mjs?v=20260822-source-authority1";
import { removeExpiredDatedEvents } from "./runtime-past-event-guard.mjs?v=20260823-pastguard4";
import { applyProgramVisibilityPolicy } from "./program-visibility-policy.js?v=20260820-programs4";
import { publishAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";

const LOS_FANTASMAS_EVENT_ID = "agenda_bc147abef119a17edb8a9770";
const SOURCE_DISPLAY_NAMES = Object.freeze({
  culturasvina: "Visita Viña — Municipalidad de Viña del Mar",
});
const PROCESSED_CACHE_PREFIX = "vivamos-processed-pipeline-";

export function normalizeSourceDisplayNames(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    const sourceId = String(event?.source_id || "").trim();
    const displayName = SOURCE_DISPLAY_NAMES[sourceId];
    if (!displayName) return event;

    const sourceName = String(event?.source_name || "").trim();
    const organizer = String(event?.organizer || "").trim();
    const organizerMirrorsSource = !organizer || organizer === sourceName || organizer === "Culturas Viña";
    if (sourceName === displayName && (!organizerMirrorsSource || organizer === displayName)) return event;

    changed = true;
    return {
      ...event,
      source_name: displayName,
      organizer: organizerMirrorsSource ? displayName : event.organizer,
    };
  });
  return changed ? { ...dataset, events } : dataset;
}

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

function localDateKey(now, timeZone) {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: timeZone || "UTC",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(now);
    const get = (type) => parts.find((part) => part.type === type)?.value;
    return `${get("year")}-${get("month")}-${get("day")}`;
  } catch {
    return now.toISOString().slice(0, 10);
  }
}

function payloadSignature(payload, status = "ok") {
  const events = Array.isArray(payload?.events) ? payload.events : [];
  const middle = events.length ? events[Math.floor(events.length / 2)] : null;
  return {
    status,
    schema_version: String(payload?.schema_version || ""),
    generated_at: String(payload?.generated_at || ""),
    publication_date: String(payload?.publication_date || ""),
    counts: payload?.counts || null,
    event_count: events.length,
    first_id: String(events[0]?.id || ""),
    middle_id: String(middle?.id || ""),
    last_id: String(events[events.length - 1]?.id || ""),
  };
}

function buildSourceSignature(city, base, supplementalResult, now) {
  const supplemental = supplementalResult?.status === "ok" ? supplementalResult.payload : null;
  return JSON.stringify({
    city: String(city?.id || ""),
    day: localDateKey(now, city?.timezone || base?.timezone || "UTC"),
    base: payloadSignature(base, "ok"),
    supplemental: supplemental
      ? payloadSignature(supplemental, "ok")
      : payloadSignature(null, supplementalResult?.status || "absent"),
  });
}

function processedCacheName() {
  const release = Number(globalThis.__VIVAMOS_RELEASE__);
  return `${PROCESSED_CACHE_PREFIX}${Number.isFinite(release) ? `v${release}` : "dev"}`;
}

function processedCacheMarkerKey(city) {
  return `${PROCESSED_CACHE_PREFIX}marker-${encodeURIComponent(String(city?.id || "default"))}`;
}

function readProcessedMarker(city) {
  try {
    const raw = globalThis.localStorage?.getItem(processedCacheMarkerKey(city));
    if (!raw) return null;
    const marker = JSON.parse(raw);
    return marker && typeof marker === "object" ? marker : null;
  } catch {
    return null;
  }
}

function writeProcessedMarker(city, cacheName, signature) {
  try {
    globalThis.localStorage?.setItem(processedCacheMarkerKey(city), JSON.stringify({ cacheName, signature }));
  } catch {
    // The processed cache is an optimization only; storage may be unavailable.
  }
}

function clearProcessedMarker(city) {
  try {
    globalThis.localStorage?.removeItem(processedCacheMarkerKey(city));
  } catch {
    // Best-effort cleanup only.
  }
}

function processedCacheRequest(city) {
  if (typeof Request !== "function" || !globalThis.location?.href) return null;
  try {
    const url = new URL(
      `./__processed-pipeline-cache__/${encodeURIComponent(String(city?.id || "default"))}.json`,
      globalThis.location.href,
    );
    return new Request(url.href, { method: "GET" });
  } catch {
    return null;
  }
}

async function readProcessedResult(city, signature) {
  if (!globalThis.caches?.open) return null;
  const cacheName = processedCacheName();
  const marker = readProcessedMarker(city);
  if (marker?.cacheName !== cacheName || marker?.signature !== signature) return null;

  const request = processedCacheRequest(city);
  if (!request) return null;
  try {
    const cache = await globalThis.caches.open(cacheName);
    const response = await cache.match(request);
    if (!response) {
      clearProcessedMarker(city);
      return null;
    }
    const cached = await response.json();
    if (cached?.signature !== signature) {
      clearProcessedMarker(city);
      return null;
    }
    if (!cached?.dataset || !Array.isArray(cached.dataset.events)) {
      clearProcessedMarker(city);
      return null;
    }
    return {
      dataset: cached.dataset,
      secondaryPrograms: Array.isArray(cached.secondaryPrograms) ? cached.secondaryPrograms : [],
      hiddenPrograms: Array.isArray(cached.hiddenPrograms) ? cached.hiddenPrograms : [],
    };
  } catch (error) {
    clearProcessedMarker(city);
    console.warn("¡Vivamos!: caché procesada no disponible; continúa el pipeline normal", error);
    return null;
  }
}

async function cleanupObsoleteProcessedCaches(currentName) {
  if (!globalThis.caches?.keys || !globalThis.caches?.delete) return;
  try {
    const names = await globalThis.caches.keys();
    await Promise.all(
      names
        .filter((name) => name.startsWith(PROCESSED_CACHE_PREFIX) && name !== currentName)
        .map((name) => globalThis.caches.delete(name)),
    );
  } catch {
    // Cache cleanup is best-effort and must never block agenda rendering.
  }
}

async function writeProcessedResult(city, signature, result) {
  if (!globalThis.caches?.open || typeof Response !== "function") return;
  const request = processedCacheRequest(city);
  if (!request) return;
  const cacheName = processedCacheName();
  try {
    const cache = await globalThis.caches.open(cacheName);
    const response = new Response(JSON.stringify({
      signature,
      dataset: result.dataset,
      secondaryPrograms: result.secondaryPrograms || [],
      hiddenPrograms: result.hiddenPrograms || [],
    }), {
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
    await cache.put(request, response);
    writeProcessedMarker(city, cacheName, signature);
    void cleanupObsoleteProcessedCaches(cacheName);
  } catch (error) {
    clearProcessedMarker(city);
    console.warn("¡Vivamos!: no se pudo guardar la caché procesada", error);
  }
}

async function loadPayloads(city, fetchImpl, diagnostics, now) {
  const supplementalUrl = String(city?.supplemental_dataset || "").trim();
  const basePromise = fetchJson(city.dataset, fetchImpl);
  const supplementalPromise = supplementalUrl
    ? fetchJson(supplementalUrl, fetchImpl).then(
      (payload) => ({ status: "ok", payload }),
      (error) => ({ status: "error", error }),
    )
    : Promise.resolve({ status: "absent" });

  const [base, supplementalResult] = await Promise.all([basePromise, supplementalPromise]);
  diagnostics.push({ name: "base", status: "ok" });

  let dataset = base;
  if (supplementalResult.status === "ok") {
    diagnostics.push({ name: "supplemental", status: "ok" });
    dataset = mergeSupplementalPayload(base, supplementalResult.payload);
  } else if (supplementalResult.status === "error") {
    diagnostics.push({
      name: "supplemental",
      status: "skipped",
      error: String(supplementalResult.error?.message || supplementalResult.error),
    });
    console.warn(
      "¡Vivamos!: eventos suplementarios no disponibles; continúa el dataset principal",
      supplementalResult.error,
    );
  }

  return {
    dataset,
    sourceSignature: buildSourceSignature(city, base, supplementalResult, now),
  };
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
  const payloadResult = await loadPayloads(city, fetchImpl, diagnostics, now);
  let dataset = payloadResult.dataset;
  const cacheEligible = fetchImpl === globalThis.fetch && globalThis.caches?.open;

  if (cacheEligible) {
    const cached = await readProcessedResult(city, payloadResult.sourceSignature);
    if (cached) {
      diagnostics.push({ name: "processed-pipeline-cache", status: "hit" });
      const result = { ...cached, diagnostics };
      publishAgendaRuntimeSnapshot(city, result);
      return result;
    }
    diagnostics.push({ name: "processed-pipeline-cache", status: "miss" });
  }

  dataset = applyStage("public-text-sanitizer", normalizeAgendaPublicText, dataset, diagnostics);
  dataset = applyStage("source-display-name-normalizer", normalizeSourceDisplayNames, dataset, diagnostics);
  if (city.id === "valparaiso") {
    dataset = applyStage("event-data-corrections", applyEventDataCorrections, dataset, diagnostics);
  } else {
    diagnostics.push({ name: "event-data-corrections", status: "not-applicable" });
  }
  dataset = applyStage("title-recovery", recoverAgendaTitles, dataset, diagnostics);
  dataset = applyStage("category-normalizer", normalizeAgendaCategories, dataset, diagnostics);
  dataset = applyStage("venue-identity-normalizer", (current) => ({
    ...current,
    events: normalizeVenueAliases(current.events),
  }), dataset, diagnostics);
  if (city.id === "valparaiso") {
    dataset = applyStage("known-publication-categories", applyKnownPublicationCategories, dataset, diagnostics);
  } else {
    diagnostics.push({ name: "known-publication-categories", status: "not-applicable" });
  }
  dataset = applyStage("title-normalizer", normalizeAgendaTitles, dataset, diagnostics);
  dataset = applyStage("session-occurrence-normalizer", normalizeSessionOccurrences, dataset, diagnostics);
  dataset = applyStage("formation-lifecycle-classifier", normalizeFormationCycles, dataset, diagnostics);
  if (city.id === "valparaiso") {
    dataset = applyStage("artequin-session-correction", correctArtequinNaturalArtSessions, dataset, diagnostics);
  } else {
    diagnostics.push({ name: "artequin-session-correction", status: "not-applicable" });
  }
  dataset = applyStage("cross-source-deduplication", deduplicateCrossSourceDataset, dataset, diagnostics);
  // City-specific corroborations become structured evidence here. They do not
  // write public source fields; the next stage is the only canonical chooser.
  dataset = applyStage("city-source-evidence-adapter", (current) => ({
    ...current,
    events: current.events.map((event) => enrichCitySourceEvidence(event, city.id)),
  }), dataset, diagnostics);
  dataset = applyStage("source-evidence-normalizer", normalizeAgendaSourceEvidence, dataset, diagnostics);
  dataset = applyStage(
    "past-event-guard",
    (current) => removeExpiredDatedEvents(current, {
      now,
      timeZone: city.timezone || current?.timezone || "UTC",
    }),
    dataset,
    diagnostics,
  );
  dataset = applyStage("public-text-sanitizer-final", normalizeAgendaPublicText, dataset, diagnostics);

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
    referenceNow: now,
  };
  publishAgendaRuntimeSnapshot(city, result);
  if (cacheEligible) void writeProcessedResult(city, payloadResult.sourceSignature, result);
  return result;
}
