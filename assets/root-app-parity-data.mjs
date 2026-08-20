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
 * Adaptador exclusivo de la WEB raíz.
 * Consume la lógica de publicación de APP sin modificar ningún archivo de APP.
 */
export async function loadRootPublicAgenda({ fetchImpl = globalThis.fetch, now = new Date() } = {}) {
  return loadAgendaDataset(ROOT_CITY, { fetchImpl, now });
}

export async function loadRootPublicDataset(options = {}) {
  const result = await loadRootPublicAgenda(options);
  return result.dataset;
}
