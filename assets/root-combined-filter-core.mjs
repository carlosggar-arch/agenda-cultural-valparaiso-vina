import { resolveRootPublicCategory } from "./root-public-category-rules.mjs?v=20260820-webcat2";

const LOS_FANTASMAS_EVENT_ID = "agenda_bc147abef119a17edb8a9770";

export const ROOT_SEARCH_ALIASES = Object.freeze({
  valpo: ["valpo", "valparaiso"],
  valparaiso: ["valparaiso", "valpo"],
  vina: ["vina", "vina del mar"],
  gratis: ["gratis", "gratuito", "gratuita", "liberado", "liberada"],
  gratuito: ["gratis", "gratuito", "gratuita", "liberado", "liberada"],
  inscripcion: ["inscripcion", "registro", "reserva"],
  registro: ["inscripcion", "registro", "reserva"],
  reserva: ["inscripcion", "registro", "reserva"],
  entrada: ["entrada", "entradas", "ticket", "tickets"],
  entradas: ["entrada", "entradas", "ticket", "tickets"],
  ticket: ["entrada", "entradas", "ticket", "tickets"],
  tickets: ["entrada", "entradas", "ticket", "tickets"],
  online: ["online", "virtual", "en linea"],
  virtual: ["online", "virtual", "en linea"],
  familiar: ["familiar", "familia", "familias", "infantil", "ninos", "ninas", "todo publico", "todas las edades"],
  familia: ["familiar", "familia", "familias", "infantil", "ninos", "ninas", "todo publico", "todas las edades"],
  infantil: ["familiar", "familia", "infantil", "ninos", "ninas"],
});

const CATEGORY_ALIASES = new Map([
  ["museo", "exposiciones"],
  ["museos", "exposiciones"],
  ["exposicion", "exposiciones"],
  ["feria", "ferias-gastronomia"],
  ["ferias", "ferias-gastronomia"],
  ["gastronomia", "ferias-gastronomia"],
  ["naturaleza", "naturaleza-deportes"],
  ["naturaleza-montana", "naturaleza-deportes"],
  ["deportes", "naturaleza-deportes"],
  ["talleres", "cursos-talleres"],
]);

export function normalizeRootSearchText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es-CL")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function hasRegistration(event) {
  return Boolean(
    String(event?.links?.registration || "").trim()
    || event?.public_status?.registration_open === true
    || String(event?.registration_requirements || "").trim()
  );
}

function hasTickets(event) {
  return Boolean(String(event?.links?.tickets || "").trim());
}

function isOnline(event) {
  return event?.location?.online === true
    || /\b(?:online|virtual|en linea)\b/.test(normalizeRootSearchText([
      event?.location?.venue,
      event?.location?.address,
      event?.description,
    ].filter(Boolean).join(" ")));
}

function isFamilyFriendly(event) {
  const text = normalizeRootSearchText([
    event?.audience,
    ...(event?.tags || []),
    event?.title,
    event?.description,
  ].filter(Boolean).join(" "));
  return /\bfamiliar(?:es)?\b|\bfamilias?\b|\binfantil(?:es)?\b|\bninos?\b|\bninas?\b|\btodo publico\b|\btodas las edades\b/.test(text);
}

export function rootEventPublicCategories(event) {
  if (String(event?.id || "") === LOS_FANTASMAS_EVENT_ID) {
    return [{ id: "teatro", label: "Teatro" }];
  }
  const category = resolveRootPublicCategory(event);
  return [category || { id: "otros", label: "Otros panoramas" }];
}

export function rootEventCategoryIds(event) {
  return new Set(rootEventPublicCategories(event).map((category) => String(category?.id || "")).filter(Boolean));
}

export function rootEventSearchText(event) {
  const derived = [];
  if (event?.price?.is_free === true) derived.push("gratis gratuito gratuita liberado liberada");
  if (hasRegistration(event)) derived.push("inscripcion registro reserva");
  if (hasTickets(event)) derived.push("entrada entradas ticket tickets");
  if (isOnline(event)) derived.push("online virtual en linea");
  else derived.push("presencial");
  if (isFamilyFriendly(event)) derived.push("familiar familia familias infantil ninos ninas todo publico todas las edades");

  return normalizeRootSearchText([
    event?.title,
    event?.description,
    event?.organizer,
    event?.source_name,
    event?.source_id,
    event?.location?.venue,
    event?.location?.address,
    event?.location?.city,
    event?.location?.commune,
    event?.audience,
    event?.price?.display_text,
    event?.schedule?.display_text,
    ...(event?.tags || []),
    ...rootEventPublicCategories(event).flatMap((category) => [category?.id, category?.label]),
    ...derived,
  ].filter(Boolean).join(" "));
}

function queryAlternatives(token) {
  return ROOT_SEARCH_ALIASES[token] || [token];
}

export function rootEventMatchesQuery(event, query) {
  const tokens = normalizeRootSearchText(query).split(" ").filter(Boolean);
  if (!tokens.length) return true;
  const haystack = rootEventSearchText(event);
  return tokens.every((token) => queryAlternatives(token).some((candidate) => haystack.includes(candidate)));
}

function canonicalCategoryId(value) {
  const id = String(value || "").trim().toLocaleLowerCase("es-CL");
  if (id === "cultura") return "";
  return CATEGORY_ALIASES.get(id) || id;
}

export function rootEventMatchesCategories(event, selectedCategories) {
  const selected = selectedCategories instanceof Set ? selectedCategories : new Set(selectedCategories || []);
  const canonicalSelected = [...selected].map(canonicalCategoryId).filter(Boolean);
  if (!canonicalSelected.length) return true;
  const eventCategories = rootEventCategoryIds(event);
  return canonicalSelected.some((categoryId) => eventCategories.has(categoryId));
}

export function rootEventMatchesAccess(event, access = "todos") {
  if (access === "entradas") return hasTickets(event);
  if (access === "inscripcion") return hasRegistration(event);
  return true;
}

export function rootEventMatchesFormat(event, format = "todos") {
  if (format === "en-linea") return isOnline(event);
  if (format === "presencial") return !isOnline(event);
  return true;
}

export function rootEventMatchesAudience(event, audience = "todos") {
  if (audience === "familiar") return isFamilyFriendly(event);
  return true;
}

export function rootEventMatchesPrice(event, price = "todos") {
  if (price === "gratis") return event?.price?.is_free === true;
  if (price === "pagado") return event?.price?.is_free === false || Number(event?.price?.min_amount || 0) > 0;
  return true;
}

export function rootEventMatchesAdvancedFilters(event, filters = {}) {
  return rootEventMatchesQuery(event, filters.query || "")
    && rootEventMatchesCategories(event, filters.categories || [])
    && rootEventMatchesAccess(event, filters.access || "todos")
    && rootEventMatchesFormat(event, filters.format || "todos")
    && rootEventMatchesAudience(event, filters.audience || "todos")
    && rootEventMatchesPrice(event, filters.price || "todos");
}

export function filterRootEvents(events, filters = {}) {
  return (events || []).filter((event) => rootEventMatchesAdvancedFilters(event, filters));
}
