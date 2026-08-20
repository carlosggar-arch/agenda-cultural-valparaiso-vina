import { loadAgendaDataset } from "../app/data-pipeline.js?v=20260820-root-consumer1";

const ROOT_CITY = Object.freeze({
  id: "valparaiso",
  label: "Valparaíso / Viña del Mar",
  timezone: "America/Santiago",
  locale: "es-CL",
  dataset: "./agenda_web.json",
  supplemental_dataset: "./app/data/valparaiso/supplemental-events.json",
});

/**
 * Root-WEB data adapter.
 *
 * The APP pipeline remains the single source of truth for publication cleanup
 * (corrections, category/title normalization, session normalization,
 * cross-source deduplication, expired-event removal and program visibility).
 * This file only consumes that pipeline; no APP file is modified by the WEB.
 */
export async function loadRootPublicAgenda({ fetchImpl = globalThis.fetch, now = new Date() } = {}) {
  return loadAgendaDataset(ROOT_CITY, { fetchImpl, now });
}

export async function loadRootPublicDataset(options = {}) {
  const result = await loadRootPublicAgenda(options);
  return result.dataset;
}
