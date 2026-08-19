const BIENAL_EVENT_ID = "agenda_970a461a24590f90dad68803";
const BIENAL_TITLE_PATTERN = /segunda\s+bienal\s+de\s+danza/i;

const MISSING_BIENAL_DATES = Object.freeze([
  Object.freeze({
    date: "2026-08-20",
    start: "2026-08-20T19:00:00-04:00",
    displayText: "20-08-2026 · 19:00",
    id: "agenda_pcdv_bienal_20260820",
    title: "Segunda Bienal de Danza — La Fuga + Compañía Consecuencia",
    description: "Cooperativa de Artes Escénicas La Fuga — “Mi sombra en azul de un reflejo”; Compañía Consecuencia — “18.0 cenizas de la revuelta”.",
  }),
  Object.freeze({
    date: "2026-08-21",
    start: "2026-08-21T19:00:00-04:00",
    displayText: "21-08-2026 · 19:00",
    id: "agenda_pcdv_bienal_20260821",
    title: "Segunda Bienal de Danza — hangar_espacio_ — Estado #3",
    description: "hangar_espacio_ presenta “Estado #3” en la Segunda Bienal de Danza Moderna y Contemporánea de la Región de Valparaíso.",
  }),
]);

function isBienalEvent(event) {
  if (!event || typeof event !== "object") return false;
  if (event.id === BIENAL_EVENT_ID) return true;
  const source = String(event.source_url || event?.links?.official || event?.links?.source || "");
  return source.includes("parquecultural.cl/") && BIENAL_TITLE_PATTERN.test(String(event.title || ""));
}

function eventDateKeys(event) {
  const occurrences = Array.isArray(event?.schedule?.occurrences) ? event.schedule.occurrences : [];
  const starts = occurrences.length
    ? occurrences.map((occurrence) => occurrence?.start)
    : [event?.schedule?.start];
  return new Set(starts
    .map((value) => String(value || "").slice(0, 10))
    .filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value)));
}

function cloneBienalDate(baseEvent, correction) {
  const tags = new Set([...(baseEvent.tags || []), "danza", "bienal"]);
  return {
    ...baseEvent,
    id: correction.id,
    title: correction.title,
    description: correction.description,
    schedule: {
      ...(baseEvent.schedule || {}),
      mode: "dated",
      start: correction.start,
      end: null,
      timezone: "America/Santiago",
      display_text: correction.displayText,
      occurrences: [{ start: correction.start, end: null }],
    },
    tags: [...tags],
    editorial: {
      ...(baseEvent.editorial || {}),
      correction: "official_program_multidate_recovery",
      correction_parent_id: baseEvent.id,
    },
  };
}

function recalculateCounts(events, originalCounts = {}) {
  const counts = { ...originalCounts };
  counts.total = events.length;
  counts.events = events.filter((event) => !["program", "flexible_offer", "course"].includes(event?.event_type)).length;
  counts.courses = events.filter((event) => event?.event_type === "course").length;
  counts.flexible_offers = events.filter((event) => event?.event_type === "flexible_offer").length;
  counts.programs = events.filter((event) => event?.event_type === "program").length;
  return counts;
}

export function applyEventDataCorrections(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;

  const baseEvent = dataset.events.find(isBienalEvent);
  if (!baseEvent) return dataset;

  const events = [...dataset.events];
  let changed = false;

  for (const correction of MISSING_BIENAL_DATES) {
    const alreadyPresent = events.some((event) => isBienalEvent(event) && eventDateKeys(event).has(correction.date));
    if (alreadyPresent) continue;
    events.push(cloneBienalDate(baseEvent, correction));
    changed = true;
  }

  if (!changed) return dataset;
  return {
    ...dataset,
    events,
    counts: recalculateCounts(events, dataset.counts),
  };
}

function isAgendaDatasetRequest(input, response) {
  const urls = [response?.url, typeof input === "string" ? input : input?.url].filter(Boolean);
  return urls.some((value) => /(?:^|\/)agenda_web\.json(?:[?#]|$)/.test(String(value)));
}

export function installEventDataCorrections(target = globalThis) {
  if (!target || typeof target.fetch !== "function" || target.__vivamosEventDataCorrectionsInstalled) return;

  const nativeFetch = target.fetch.bind(target);
  target.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    if (!response?.ok || !isAgendaDatasetRequest(args[0], response)) return response;

    let dataset;
    try {
      dataset = await response.clone().json();
    } catch {
      return response;
    }

    const corrected = applyEventDataCorrections(dataset);
    if (corrected === dataset) return response;

    const headers = new Headers(response.headers);
    headers.delete("content-length");
    headers.delete("content-encoding");
    headers.set("content-type", "application/json; charset=utf-8");
    return new Response(JSON.stringify(corrected), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  };

  Object.defineProperty(target, "__vivamosEventDataCorrectionsInstalled", {
    value: true,
    configurable: false,
    enumerable: false,
    writable: false,
  });
}

if (typeof window !== "undefined") installEventDataCorrections(window);
