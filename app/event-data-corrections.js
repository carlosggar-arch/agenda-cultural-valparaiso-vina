const BIENAL_EVENT_ID = "agenda_970a461a24590f90dad68803";
const BIENAL_TITLE_PATTERN = /segunda\s+bienal\s+de\s+danza/i;
const RIOJA_LISTING_URL = "https://visitavina.munivina.cl/actividades/";

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

const RIOJA_CORRECTIONS = Object.freeze([
  { id: "agenda_rioja_20260819_qigong", title: "Taller // Qi Gong", date: "2026-08-19", start: "2026-08-19T10:00:00-04:00", end: null, venue: "Jardines Palacio Rioja", category: ["cursos-talleres", "Cursos y talleres"] },
  { id: "agenda_rioja_20260819_mitio", title: "Ciclo de Cine de Autor // Jacques Tati, “Mi tío”", date: "2026-08-19", start: "2026-08-19T16:00:00-04:00", end: "2026-08-19T18:00:00-04:00", venue: "Palacio Rioja, Sala Aldo Francia", category: ["cine", "Cine"] },
  { id: "agenda_rioja_20260820_visita_mar_dulce", title: "Visita guiada exposición // “A veces un mar dulce”", date: "2026-08-20", start: "2026-08-20T15:00:00-04:00", end: "2026-08-20T17:00:00-04:00", venue: "Palacio Rioja", category: ["exposiciones", "Exposiciones"], isFree: true },
  { id: "agenda_rioja_20260821_hilos", title: "Taller // Expresión textil: Moviendo Hilos", date: "2026-08-21", start: "2026-08-21T15:00:00-04:00", end: "2026-08-21T16:30:00-04:00", venue: "Palacio Rioja", category: ["cursos-talleres", "Cursos y talleres"] },
  { id: "agenda_rioja_20260822_hilos", title: "Taller // Expresión textil: Moviendo Hilos", date: "2026-08-22", start: "2026-08-22T15:00:00-04:00", end: "2026-08-22T16:30:00-04:00", venue: "Palacio Rioja", category: ["cursos-talleres", "Cursos y talleres"] },
  { id: "agenda_rioja_20260825_angel", title: "Travesías Cinematográfica FICVIÑA // “El ángel exterminador”", date: "2026-08-25", start: "2026-08-25T16:00:00-04:00", end: "2026-08-25T18:00:00-04:00", venue: "Sala Aldo Francia", category: ["cine", "Cine"] },
  { id: "agenda_rioja_20260826_qigong", title: "Taller // Qi Gong", date: "2026-08-26", start: "2026-08-26T10:00:00-04:00", end: null, venue: "Jardines Palacio Rioja", category: ["cursos-talleres", "Cursos y talleres"] },
  { id: "agenda_rioja_20260826_playtime", title: "Ciclo de Cine de Autor // Jacques Tati, “Playtime”", date: "2026-08-26", start: "2026-08-26T16:00:00-04:00", end: "2026-08-26T18:00:00-04:00", venue: "Palacio Rioja, Sala Aldo Francia", category: ["cine", "Cine"] },
  { id: "agenda_rioja_20260827_museo_manos", title: "Taller // El Museo en tus manos", date: "2026-08-27", start: "2026-08-27T16:00:00-04:00", end: "2026-08-27T17:00:00-04:00", venue: "Jardines Palacio Rioja", category: ["cursos-talleres", "Cursos y talleres"] },
  { id: "agenda_rioja_20260827_decadencia", title: "Presentación libro // “Decadencia”", date: "2026-08-27", start: "2026-08-27T17:00:00-04:00", end: "2026-08-27T19:00:00-04:00", venue: "Palacio Rioja", category: ["cultura", "Cultura"] },
  { id: "agenda_rioja_20260828_consome", title: "Presentación libro // “Consomé Punk”", date: "2026-08-28", start: "2026-08-28T18:00:00-04:00", end: "2026-08-28T20:00:00-04:00", venue: "Palacio Rioja, Sala Aldo Francia", category: ["cultura", "Cultura"] },
  { id: "agenda_rioja_20260829_hilos", title: "Taller // Expresión textil: Moviendo Hilos", date: "2026-08-29", start: "2026-08-29T15:00:00-04:00", end: "2026-08-29T16:30:00-04:00", venue: "Palacio Rioja", category: ["cursos-talleres", "Cursos y talleres"] },
  { id: "agenda_rioja_20260829_moncho", title: "Concierto jazz // Moncho Pérez", date: "2026-08-29", start: "2026-08-29T19:00:00-04:00", end: "2026-08-29T21:00:00-04:00", venue: "Palacio Rioja, Sala Aldo Francia", category: ["musica", "Música"] },
]);

function isBienalEvent(event) {
  if (!event || typeof event !== "object") return false;
  if (event.id === BIENAL_EVENT_ID) return true;
  const source = String(event.source_url || event?.links?.official || event?.links?.source || "");
  return source.includes("parquecultural.cl/") && BIENAL_TITLE_PATTERN.test(String(event.title || ""));
}

function eventDateKeys(event) {
  const occurrences = Array.isArray(event?.schedule?.occurrences) ? event.schedule.occurrences : [];
  const starts = occurrences.length ? occurrences.map((occurrence) => occurrence?.start) : [event?.schedule?.start];
  return new Set(starts.map((value) => String(value || "").slice(0, 10)).filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value)));
}

function titleKey(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es").replace(/[^a-z0-9]+/g, " ").trim();
}

function cloneBienalDate(baseEvent, correction) {
  const tags = new Set([...(baseEvent.tags || []), "danza", "bienal"]);
  return {
    ...baseEvent,
    id: correction.id,
    title: correction.title,
    description: correction.description,
    schedule: { ...(baseEvent.schedule || {}), mode: "dated", start: correction.start, end: null, timezone: "America/Santiago", display_text: correction.displayText, occurrences: [{ start: correction.start, end: null }] },
    tags: [...tags],
    editorial: { ...(baseEvent.editorial || {}), correction: "official_program_multidate_recovery", correction_parent_id: baseEvent.id },
  };
}

function riojaEvent(correction) {
  const [categoryId, categoryLabel] = correction.category;
  const isFree = correction.isFree === true;
  return {
    id: correction.id,
    title: correction.title,
    event_type: "event",
    primary_category: { id: categoryId, label: categoryLabel },
    categories: [{ id: categoryId, label: categoryLabel }],
    schedule: { mode: "dated", start: correction.start, end: correction.end, timezone: "America/Santiago", display_text: `${correction.date} · ${correction.start.slice(11, 16)}${correction.end ? `–${correction.end.slice(11, 16)}` : ""}`, occurrences: [] },
    location: { venue_id: "museo_palacio_rioja", city: "Viña del Mar", commune: "Viña del Mar", venue: correction.venue, address: "Quillota 214, Viña del Mar", online: false, latitude: null, longitude: null },
    price: { is_free: isFree ? true : null, currency: "CLP", min_amount: isFree ? 0 : null, max_amount: isFree ? 0 : null, display_text: isFree ? "Gratis" : "Consultar condiciones" },
    links: { official: RIOJA_LISTING_URL, tickets: null, registration: null, source: RIOJA_LISTING_URL },
    organizer: "Museo Palacio Rioja",
    source_id: "museo_palacio_rioja",
    source_name: "Museo Palacio Rioja",
    source_url: RIOJA_LISTING_URL,
    public_status: { source_official: true, cancelled: false, price_confirmed: isFree, information_completeness: "complete", advisory_text: "Actividad confirmada en la cartelera oficial municipal Visita Viña; la fuente institucional del museo es @museopalaciorioja." },
    description: "Actividad del Museo Palacio Rioja confirmada en la cartelera oficial municipal de Viña del Mar.",
    tags: [categoryLabel, "Museo Palacio Rioja", "Visita Viña"],
    audience: null,
    registration_requirements: null,
    image: { url: null, alt: null },
    editorial: { classification: "event", reason: "publication_safety:palacio_rioja", covered_source_ids: ["museo_palacio_rioja"] },
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
  const events = [...dataset.events];
  let changed = false;

  const baseEvent = events.find(isBienalEvent);
  if (baseEvent) {
    for (const correction of MISSING_BIENAL_DATES) {
      const alreadyPresent = events.some((event) => isBienalEvent(event) && eventDateKeys(event).has(correction.date));
      if (alreadyPresent) continue;
      events.push(cloneBienalDate(baseEvent, correction));
      changed = true;
    }
  }

  for (const correction of RIOJA_CORRECTIONS) {
    const key = titleKey(correction.title);
    const alreadyPresent = events.some((event) => eventDateKeys(event).has(correction.date) && titleKey(event?.title) === key);
    if (alreadyPresent) continue;
    events.push(riojaEvent(correction));
    changed = true;
  }

  if (!changed) return dataset;
  return { ...dataset, events, counts: recalculateCounts(events, dataset.counts) };
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
    try { dataset = await response.clone().json(); } catch { return response; }
    const corrected = applyEventDataCorrections(dataset);
    if (corrected === dataset) return response;
    const headers = new Headers(response.headers);
    headers.delete("content-length"); headers.delete("content-encoding"); headers.set("content-type", "application/json; charset=utf-8");
    return new Response(JSON.stringify(corrected), { status: response.status, statusText: response.statusText, headers });
  };
  Object.defineProperty(target, "__vivamosEventDataCorrectionsInstalled", { value: true, configurable: false, enumerable: false, writable: false });
}

if (typeof window !== "undefined") installEventDataCorrections(window);
