import * as base from "./agenda-core-base.mjs";

export * from "./agenda-core-base.mjs";

const ROOT_TIME_ZONE = base.DISPLAY_TIME_ZONE || "America/Santiago";

const ROOT_CATEGORY_ALIASES = new Map([
  ["ferias", "ferias-gastronomia"],
  ["gastronomia", "ferias-gastronomia"],
  ["naturaleza", "naturaleza-deportes"],
  ["naturaleza-montana", "naturaleza-deportes"],
  ["deportes", "naturaleza-deportes"],
  ["museos", "exposiciones"],
]);

const ROOT_CATEGORY_LABELS = new Map([
  ["ferias-gastronomia", "Ferias y gastronomía"],
  ["naturaleza-deportes", "Naturaleza y deportes"],
  ["exposiciones", "Exposiciones y museos"],
  ["otros", "Otros panoramas"],
]);

const CULTURE_CATEGORY_RULES = [
  ["musica", "Música", /\b(musica|musical|concierto|recital|jazz|orquesta|coro|tocata|banda|cantautor|cantante|sinfon|sonoro|payada)\b/],
  ["cine", "Cine", /\b(cine|pelicula|film|documental|cortometraje|largometraje|audiovisual|proyeccion)\b/],
  ["teatro", "Teatro", /\b(teatro|teatral|obra|dramaturg|escena|danza|ballet|circo|performance|actor|actriz)\b/],
  ["exposiciones", "Exposiciones y museos", /\b(museo|exposicion|exhibicion|muestra|galeria|patrimonio|fotografia|pintura|escultura|artes visuales|visita guiada)\b/],
  ["cursos-talleres", "Cursos y talleres", /\b(taller|curso|seminario|charla|conversatorio|capacitacion|laboratorio|workshop|ponencia)\b/],
  ["naturaleza-deportes", "Naturaleza y deportes", /\b(naturaleza|trekking|senderismo|caminata|montana|cerro|deporte|deportivo|yoga|ciclismo|bicicleta|kayak|surf|ecologia|ecosistema)\b/],
  ["ferias-gastronomia", "Ferias y gastronomía", /\b(feria|gastronomia|gastronomico|comida|cocina|mercado|degustacion|restaurante|cafe)\b/],
];

function normalizeCategoryText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es-CL")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function canonicalRootCategory(category) {
  const rawId = String(category?.id || "").trim().toLocaleLowerCase("es-CL");
  if (!rawId || rawId === "cultura") return null;
  const id = ROOT_CATEGORY_ALIASES.get(rawId) || rawId;
  return {
    id,
    label: ROOT_CATEGORY_LABELS.get(id) || category?.label || id,
  };
}

function inferredCultureCategories(event) {
  const text = normalizeCategoryText([
    event?.title,
    event?.description,
    event?.organizer,
    event?.source_name,
    event?.location?.venue,
    ...(event?.tags || []),
  ].filter(Boolean).join(" "));
  const inferred = [];
  for (const [id, label, pattern] of CULTURE_CATEGORY_RULES) {
    if (pattern.test(text)) inferred.push({ id, label });
  }
  return inferred.length ? inferred : [{ id: "otros", label: "Otros panoramas" }];
}

export function normalizeRootEventCategories(event) {
  const categories = new Map();
  let hadCulture = false;

  for (const category of event?.categories || []) {
    if (String(category?.id || "").trim().toLocaleLowerCase("es-CL") === "cultura") {
      hadCulture = true;
      continue;
    }
    const normalized = canonicalRootCategory(category);
    if (normalized && !categories.has(normalized.id)) categories.set(normalized.id, normalized);
  }

  if (String(event?.primary_category?.id || "").trim().toLocaleLowerCase("es-CL") === "cultura") {
    hadCulture = true;
  }

  if (hadCulture && categories.size === 0) {
    for (const category of inferredCultureCategories(event)) categories.set(category.id, category);
  }

  if (categories.size === 0) {
    const primary = canonicalRootCategory(event?.primary_category);
    if (primary) categories.set(primary.id, primary);
  }

  if (categories.size === 0) categories.set("otros", { id: "otros", label: "Otros panoramas" });

  const normalizedCategories = [...categories.values()];
  const rawPrimaryId = String(event?.primary_category?.id || "").trim().toLocaleLowerCase("es-CL");
  const canonicalPrimaryId = ROOT_CATEGORY_ALIASES.get(rawPrimaryId) || rawPrimaryId;
  const primary = categories.get(canonicalPrimaryId) || normalizedCategories[0];

  return {
    ...event,
    primary_category: primary,
    categories: normalizedCategories,
  };
}

export function normalizeRootEvents(events) {
  return (events || []).map(normalizeRootEventCategories);
}

export function collectCategories(events) {
  return base.collectCategories(normalizeRootEvents(events));
}

function localDateKey(value, timeZone = ROOT_TIME_ZONE) {
  const text = String(value || "").trim();
  if (!text) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  const year = get("year");
  const month = get("month");
  const day = get("day");
  return year && month && day ? `${year}-${month}-${day}` : null;
}

function finalScheduleValues(event) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.length) {
    return occurrences.map((occurrence) => occurrence?.end || occurrence?.start).filter(Boolean);
  }
  const end = event?.schedule?.end || event?.schedule?.start;
  return end ? [end] : [];
}

export function eventIsCurrentOrFuture(event, now = new Date(), timeZone = ROOT_TIME_ZONE) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return true;
  const today = localDateKey(now, timeZone);
  if (!today) return true;
  const endDates = finalScheduleValues(event)
    .map((value) => localDateKey(value, timeZone))
    .filter(Boolean);
  if (!endDates.length) return true;
  return endDates.some((endDate) => endDate >= today);
}

export async function fetchDataset(fetchImplementation = globalThis.fetch, path = base.DATASET_PATH) {
  let response;
  try {
    response = await fetchImplementation(path, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch (error) {
    throw new base.AgendaDataError(
      "No fue posible conectar con el archivo público de la agenda.",
      "load",
      { cause: error },
    );
  }
  if (!response || !response.ok) {
    throw new base.AgendaDataError(
      `No fue posible cargar la agenda${response ? ` (HTTP ${response.status})` : ""}.`,
      "load",
    );
  }
  let data;
  try {
    data = await response.json();
  } catch (error) {
    throw new base.AgendaDataError(
      "El archivo de agenda no contiene JSON válido.",
      "load",
      { cause: error },
    );
  }
  const validated = base.validateDataset(data);
  const now = new Date();
  return {
    ...validated,
    events: normalizeRootEvents(validated.events.filter((event) => eventIsCurrentOrFuture(event, now))),
  };
}

export function eventsForSection(events, sectionId, now = new Date()) {
  return normalizeRootEvents(events).filter(
    (event) => eventIsCurrentOrFuture(event, now) && base.eventMatchesSection(event, sectionId, now),
  );
}

export function sectionCounts(events, now = new Date()) {
  return Object.fromEntries(
    base.AGENDA_SECTIONS.map(({ id }) => [id, eventsForSection(events, id, now).length]),
  );
}

export function filterEvents(events, filters = base.defaultFilterState(), now = new Date()) {
  return base.filterEvents(
    normalizeRootEvents(events).filter((event) => eventIsCurrentOrFuture(event, now)),
    filters,
    now,
  );
}
