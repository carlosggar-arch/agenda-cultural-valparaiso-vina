const CITY_CONFIG = Object.freeze({
  valparaiso: {
    locale: "es-CL",
    timezone: "America/Santiago",
    dataset: "../agenda_web.json",
  },
  gijon: {
    locale: "es-ES",
    timezone: "Europe/Madrid",
    dataset: "./data/gijon/agenda_web.json",
  },
});

const dom = {
  discovery: document.querySelector("[data-discovery]"),
  internalSearch: document.querySelector("[data-search]"),
  internalSections: document.querySelector("[data-section-filters]"),
  internalCategories: document.querySelector("[data-category-filters]"),
  search: document.querySelector("[data-smart-search]"),
  when: document.querySelector("[data-combined-when]"),
  areaGroup: document.querySelector("[data-area-filter-group]"),
  area: document.querySelector("[data-combined-area]"),
  access: document.querySelector("[data-combined-access]"),
  format: document.querySelector("[data-combined-format]"),
  audience: document.querySelector("[data-combined-audience]"),
  categories: document.querySelector("[data-combined-category-filters]"),
  customDates: document.querySelector("[data-custom-dates]"),
  dateFrom: document.querySelector("[data-date-from]"),
  dateTo: document.querySelector("[data-date-to]"),
  clear: document.querySelector("[data-filter-clear]"),
  filterSummary: document.querySelector("[data-filter-summary]"),
  agendaKicker: document.querySelector("[data-agenda-kicker]"),
  agendaTitle: document.querySelector("[data-agenda-title]"),
  total: document.querySelector("[data-total]"),
  empty: document.querySelector("[data-empty]"),
  emptyCopy: document.querySelector("[data-empty-copy]"),
  datedSection: document.querySelector("[data-dated-section]"),
  datedTotal: document.querySelector("[data-dated-total]"),
  datedGrid: document.querySelector("[data-dated-grid]"),
  programSection: document.querySelector("[data-program-section]"),
  programTotal: document.querySelector("[data-program-total]"),
  programGrid: document.querySelector("[data-program-grid]"),
  flexibleSection: document.querySelector("[data-flexible-section]"),
  flexibleTotal: document.querySelector("[data-flexible-total]"),
  flexibleGrid: document.querySelector("[data-flexible-grid]"),
};

const WHEN_LABELS = Object.freeze({
  todos: "Cualquier fecha",
  hoy: "Hoy",
  manana: "Mañana",
  "fin-de-semana": "Fin de semana",
  "7-dias": "Próximos 7 días",
  "terminan-pronto": "Terminan pronto",
  personalizado: "Rango personalizado",
});

const AREA_LABELS = Object.freeze({
  todos: "Toda la ciudad",
  valparaiso: "Valparaíso",
  vina: "Viña del Mar",
});

const ACCESS_LABELS = Object.freeze({
  todos: "Cualquier acceso",
  entradas: "Con entradas",
  inscripcion: "Con inscripción",
});

const FORMAT_LABELS = Object.freeze({
  todos: "Cualquier formato",
  presencial: "Presencial",
  "en-linea": "En línea",
});

const AUDIENCE_LABELS = Object.freeze({
  todos: "Cualquier público",
  familiar: "Para familias",
});

const SEARCH_ALIASES = Object.freeze({
  valpo: ["valpo", "valparaiso"],
  valparaiso: ["valparaiso", "valpo"],
  vina: ["vina", "vina del mar"],
  gratis: ["gratis", "gratuito", "gratuita", "liberado", "liberada"],
  gratuito: ["gratis", "gratuito", "gratuita", "liberado", "liberada"],
  gratuita: ["gratis", "gratuito", "gratuita", "liberado", "liberada"],
  inscripcion: ["inscripcion", "registro", "reserva"],
  registro: ["inscripcion", "registro", "reserva"],
  entradas: ["entradas", "tickets", "ticket"],
  ticket: ["entradas", "tickets", "ticket"],
  tickets: ["entradas", "tickets", "ticket"],
  online: ["online", "virtual", "en linea"],
  virtual: ["online", "virtual", "en linea"],
  familiar: ["familiar", "familia", "familias", "infantil", "ninos", "ninas", "todo publico", "todas las edades"],
  familia: ["familiar", "familia", "familias", "infantil", "ninos", "ninas", "todo publico", "todas las edades"],
  familias: ["familiar", "familia", "familias", "infantil", "ninos", "ninas", "todo publico", "todas las edades"],
  infantil: ["familiar", "familia", "familias", "infantil", "ninos", "ninas"],
  ninos: ["familiar", "familia", "infantil", "ninos", "ninas"],
  ninas: ["familiar", "familia", "infantil", "ninos", "ninas"],
});

const state = {
  when: "todos",
  area: "todos",
  access: "todos",
  format: "todos",
  audience: "todos",
  categories: new Set(),
  query: "",
  from: "",
  to: "",
};

let datasetEvents = [];
let loadedCity = null;
let applying = false;
let updateScheduled = false;
let updatePending = false;
let persistPending = false;
let categoryRenderSignature = "";

function currentCityId() {
  const id = document.documentElement.dataset.city;
  return CITY_CONFIG[id] ? id : "valparaiso";
}

function currentConfig() {
  return CITY_CONFIG[currentCityId()];
}

function normalizeText(value) {
  return String(value ?? "")
    .replace(/<[^>]*>/g, " ")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/\s+/g, " ")
    .trim();
}

function slugify(value) {
  return normalizeText(value)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "cultura";
}

function eventCategories(event) {
  const values = [];
  if (event?.primary_category?.id || event?.primary_category?.label) values.push(event.primary_category);
  for (const category of event?.categories || []) values.push(category);
  const unique = new Map();
  for (const category of values) {
    const label = String(category?.label || "").trim();
    const id = String(category?.id || slugify(label)).trim();
    if (label && id && !unique.has(id)) unique.set(id, label);
  }
  return unique;
}

function dateKeyForDate(date, config) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: config.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function dateKeyForValue(value, config) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : dateKeyForDate(date, config);
}

function addDays(dateKey, days) {
  const date = new Date(`${dateKey}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function weekdayForKey(dateKey) {
  return new Date(`${dateKey}T12:00:00Z`).getUTCDay();
}

function weekendBounds(todayKey) {
  const weekday = weekdayForKey(todayKey);
  const daysToSaturday = weekday === 6 ? 0 : weekday === 0 ? -1 : 6 - weekday;
  const saturday = addDays(todayKey, daysToSaturday);
  return { start: saturday, end: addDays(saturday, 1) };
}

function scheduleWindows(event) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.length) {
    return occurrences.map((occurrence) => ({
      start: occurrence?.start,
      end: occurrence?.end || occurrence?.start,
    }));
  }
  if (event?.schedule?.start) {
    return [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }];
  }
  return [];
}

function eventDateRanges(event) {
  const config = currentConfig();
  return scheduleWindows(event)
    .map((window) => ({
      start: dateKeyForValue(window.start, config),
      end: dateKeyForValue(window.end, config),
    }))
    .filter((range) => range.start && range.end);
}

function rangesOverlap(range, start, end) {
  return range.start <= end && range.end >= start;
}

function selectedDateWindow(when = state.when) {
  if (when === "todos") return null;
  const today = dateKeyForDate(new Date(), currentConfig());
  if (when === "hoy") return { start: today, end: today };
  if (when === "manana") {
    const tomorrow = addDays(today, 1);
    return { start: tomorrow, end: tomorrow };
  }
  if (when === "fin-de-semana") return weekendBounds(today);
  if (when === "7-dias") return { start: today, end: addDays(today, 6) };
  if (when === "terminan-pronto") return { start: today, end: addDays(today, 3), endingSoon: true };
  if (when === "personalizado") {
    const start = state.from || state.to;
    const end = state.to || state.from;
    if (!start || !end) return null;
    return start <= end ? { start, end } : { start: end, end: start };
  }
  return null;
}

function eventMatchesWhen(event, when = state.when) {
  if (when === "todos") return true;
  const window = selectedDateWindow(when);
  if (!window) return false;
  const ranges = eventDateRanges(event);
  if (!ranges.length) return false;
  if (window.endingSoon) {
    const today = window.start;
    return ranges.some((range) => range.start <= today && range.end > today && range.end <= window.end);
  }
  return ranges.some((range) => rangesOverlap(range, window.start, window.end));
}

function eventMatchesArea(event, area = state.area) {
  if (area === "todos" || currentCityId() !== "valparaiso") return true;
  const city = normalizeText(event?.location?.city || event?.location?.commune);
  if (area === "valparaiso") return city.includes("valparaiso");
  if (area === "vina") return city.includes("vina del mar") || city === "vina";
  return true;
}

function hasTicketLink(event) {
  return Boolean(String(event?.links?.tickets || "").trim());
}

function hasRegistration(event) {
  return Boolean(
    String(event?.links?.registration || "").trim()
    || String(event?.registration_requirements || "").trim()
    || event?.public_status?.registration_open === true
  );
}

function eventMatchesAccess(event, access = state.access) {
  if (access === "todos") return true;
  if (access === "entradas") return hasTicketLink(event);
  if (access === "inscripcion") return hasRegistration(event);
  return true;
}

function eventMatchesFormat(event, format = state.format) {
  if (format === "todos") return true;
  const online = event?.location?.online === true;
  if (format === "en-linea") return online;
  if (format === "presencial") return !online;
  return true;
}

function familySearchText(event) {
  return normalizeText([
    event?.audience,
    ...(event?.tags || []),
    event?.title,
    event?.description,
    event?.primary_category?.label,
  ].filter(Boolean).join(" "));
}

function isFamilyFriendly(event) {
  const text = familySearchText(event);
  return /\bfamiliar(?:es)?\b|\bfamilias?\b|\binfantil(?:es)?\b|\bninos?\b|\bninas?\b|\btodo publico\b|\btodas las edades\b/.test(text);
}

function eventMatchesAudience(event, audience = state.audience) {
  if (audience === "todos") return true;
  if (audience === "familiar") return isFamilyFriendly(event);
  return true;
}

function eventMatchesCategories(event, categories = state.categories) {
  if (!categories.size) return true;
  const eventIds = eventCategories(event);
  return [...categories].some((id) => eventIds.has(id));
}

function derivedSearchTerms(event) {
  const terms = [];
  if (event?.price?.is_free === true) terms.push("gratis gratuito gratuita liberado liberada");
  if (hasTicketLink(event)) terms.push("entradas ticket tickets");
  if (hasRegistration(event)) terms.push("inscripcion registro reserva");
  if (event?.location?.online === true) terms.push("online virtual en linea");
  else terms.push("presencial");
  if (isFamilyFriendly(event)) terms.push("familiar familia familias infantil ninos ninas todo publico todas las edades");
  return terms;
}

function eventSearchFields(event) {
  return {
    title: normalizeText(event?.title),
    categories: normalizeText([...eventCategories(event).values()].join(" ")),
    venue: normalizeText([event?.location?.venue, event?.location?.address, event?.location?.city, event?.location?.commune].filter(Boolean).join(" ")),
    source: normalizeText([event?.source_name, event?.source_id, event?.organizer].filter(Boolean).join(" ")),
    details: normalizeText([
      event?.description,
      ...(event?.tags || []),
      event?.audience,
      event?.price?.display_text,
      event?.schedule?.display_text,
      ...derivedSearchTerms(event),
    ].filter(Boolean).join(" ")),
  };
}

function eventSearchText(event) {
  return Object.values(eventSearchFields(event)).filter(Boolean).join(" ");
}

function queryAlternatives(token) {
  return SEARCH_ALIASES[token] || [token];
}

function eventMatchesQuery(event, query = state.query) {
  const tokens = normalizeText(query).split(" ").filter(Boolean);
  if (!tokens.length) return true;
  const haystack = eventSearchText(event);
  return tokens.every((token) => queryAlternatives(token).some((candidate) => haystack.includes(candidate)));
}

function searchScore(event, query = state.query) {
  const normalizedQuery = normalizeText(query);
  if (!normalizedQuery) return 0;
  const tokens = normalizedQuery.split(" ").filter(Boolean);
  const fields = eventSearchFields(event);
  let score = 0;

  if (fields.title === normalizedQuery) score += 1000;
  else if (fields.title.startsWith(normalizedQuery)) score += 500;
  else if (fields.title.includes(normalizedQuery)) score += 300;

  for (const token of tokens) {
    const alternatives = queryAlternatives(token);
    if (alternatives.some((value) => fields.title.includes(value))) score += 90;
    if (alternatives.some((value) => fields.categories.includes(value))) score += 55;
    if (alternatives.some((value) => fields.venue.includes(value))) score += 45;
    if (alternatives.some((value) => fields.source.includes(value))) score += 40;
    if (alternatives.some((value) => fields.details.includes(value))) score += 20;
  }

  return score;
}

function eventMatches(event, options = {}) {
  const ignore = new Set(options.ignore || []);
  if (!ignore.has("when") && !eventMatchesWhen(event)) return false;
  if (!ignore.has("area") && !eventMatchesArea(event)) return false;
  if (!ignore.has("access") && !eventMatchesAccess(event)) return false;
  if (!ignore.has("format") && !eventMatchesFormat(event)) return false;
  if (!ignore.has("audience") && !eventMatchesAudience(event)) return false;
  if (!ignore.has("categories") && !eventMatchesCategories(event)) return false;
  if (!ignore.has("query") && !eventMatchesQuery(event)) return false;
  return true;
}

function forceBaseAppFilters() {
  let changed = false;
  if (dom.internalSearch && dom.internalSearch.value) {
    dom.internalSearch.value = "";
    dom.internalSearch.dispatchEvent(new Event("input", { bubbles: true }));
    changed = true;
  }
  const allSection = dom.internalSections?.querySelector('[data-section-filter="todos"]');
  if (allSection && allSection.getAttribute("aria-pressed") !== "true") {
    allSection.click();
    changed = true;
  }
  const allCategory = dom.internalCategories?.querySelector('[data-category-filter=""]');
  if (allCategory && allCategory.getAttribute("aria-pressed") !== "true") {
    allCategory.click();
    changed = true;
  }
  return changed;
}

async function loadDataset() {
  const cityId = currentCityId();
  if (loadedCity === cityId && datasetEvents.length) return;
  loadedCity = cityId;
  datasetEvents = [];
  categoryRenderSignature = "";
  try {
    const response = await fetch(CITY_CONFIG[cityId].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    if (Array.isArray(dataset.events)) datasetEvents = dataset.events;
  } catch {
    datasetEvents = [];
  }
}

function categoryCatalog() {
  const catalog = new Map();
  for (const event of datasetEvents) {
    for (const [id, label] of eventCategories(event)) {
      if (!catalog.has(id)) catalog.set(id, label);
    }
  }
  return [...catalog.entries()]
    .map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label, currentConfig().locale));
}

function setText(node, value) {
  if (!node) return;
  const next = String(value ?? "");
  if (node.textContent !== next) node.textContent = next;
}

function setHidden(node, hidden) {
  if (node && node.hidden !== hidden) node.hidden = hidden;
}

function renderCategoryFilters() {
  if (!dom.categories) return;
  const catalog = categoryCatalog();
  const contextual = datasetEvents.filter((event) => eventMatches(event, { ignore: ["categories"] }));
  const counts = new Map(catalog.map(({ id }) => [id, 0]));
  for (const event of contextual) {
    for (const id of eventCategories(event).keys()) counts.set(id, (counts.get(id) || 0) + 1);
  }

  const rows = catalog
    .map((category) => ({
      ...category,
      count: counts.get(category.id) || 0,
      selected: state.categories.has(category.id),
    }))
    .filter((category) => category.selected || category.count > 0);
  const signature = JSON.stringify(rows);
  if (signature === categoryRenderSignature) return;
  categoryRenderSignature = signature;

  const fragment = document.createDocumentFragment();
  for (const category of rows) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.combinedCategory = category.id;
    button.className = `category-chip${category.selected ? " active" : ""}`;
    button.setAttribute("aria-pressed", category.selected ? "true" : "false");
    button.innerHTML = `<span>${escapeHtml(category.label)}</span><small>${category.count}</small>`;
    fragment.append(button);
  }
  dom.categories.replaceChildren(fragment);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setPressed(container, selector, value) {
  for (const button of container?.querySelectorAll(selector) || []) {
    const active = button.dataset.filterValue === value;
    if (button.classList.contains("active") !== active) button.classList.toggle("active", active);
    const pressed = active ? "true" : "false";
    if (button.getAttribute("aria-pressed") !== pressed) button.setAttribute("aria-pressed", pressed);
  }
}

function updateControls() {
  setPressed(dom.when, "[data-filter-value]", state.when);
  setPressed(dom.area, "[data-filter-value]", state.area);
  setPressed(dom.access, "[data-filter-value]", state.access);
  setPressed(dom.format, "[data-filter-value]", state.format);
  setPressed(dom.audience, "[data-filter-value]", state.audience);
  if (dom.search && dom.search.value !== state.query) dom.search.value = state.query;
  if (dom.dateFrom && dom.dateFrom.value !== state.from) dom.dateFrom.value = state.from;
  if (dom.dateTo && dom.dateTo.value !== state.to) dom.dateTo.value = state.to;
  setHidden(dom.customDates, state.when !== "personalizado");
  setHidden(dom.areaGroup, currentCityId() !== "valparaiso");
}

function eventSortKey(event) {
  const candidate = scheduleWindows(event)[0]?.start || event?.schedule?.start;
  if (!candidate) return Number.POSITIVE_INFINITY;
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(candidate))) return Date.parse(`${candidate}T12:00:00Z`);
  const parsed = Date.parse(candidate);
  return Number.isFinite(parsed) ? parsed : Number.POSITIVE_INFINITY;
}

function sortFilteredEvents(events) {
  return [...events].sort((a, b) => {
    if (state.query) {
      const scoreDiff = searchScore(b) - searchScore(a);
      if (scoreDiff !== 0) return scoreDiff;
    }
    const dateDiff = eventSortKey(a) - eventSortKey(b);
    if (Number.isFinite(dateDiff) && dateDiff !== 0) return dateDiff;
    return String(a?.title || "").localeCompare(String(b?.title || ""), currentConfig().locale);
  });
}

function contentGroup(event) {
  if (event?.event_type === "program") return "program";
  if (event?.event_type === "flexible_offer") return "flexible";
  return "dated";
}

function reorderCards(filtered) {
  const cards = new Map(
    [...document.querySelectorAll(".event-card[data-event-id]")]
      .map((card) => [card.dataset.eventId || "", card])
      .filter(([id]) => id),
  );
  const grids = {
    dated: dom.datedGrid,
    program: dom.programGrid,
    flexible: dom.flexibleGrid,
  };
  for (const event of filtered) {
    const card = cards.get(String(event?.id || ""));
    const grid = grids[contentGroup(event)];
    if (card && grid && card.parentElement === grid) grid.append(card);
  }
}

function visibleCards(grid) {
  return [...(grid?.querySelectorAll(".event-card") || [])].filter((card) => !card.hidden);
}

function patchGroup(section, total, grid) {
  const count = visibleCards(grid).length;
  setText(total, count);
  setHidden(section, count === 0);
  return count;
}

function activeFilterParts(total) {
  const parts = [`${total} ${total === 1 ? "actividad" : "actividades"}`];
  if (state.when !== "todos") {
    if (state.when === "personalizado" && (state.from || state.to)) {
      parts.push(`${state.from || state.to} → ${state.to || state.from}`);
    } else {
      parts.push(WHEN_LABELS[state.when]);
    }
  }
  if (currentCityId() === "valparaiso" && state.area !== "todos") parts.push(AREA_LABELS[state.area]);
  if (state.access !== "todos") parts.push(ACCESS_LABELS[state.access]);
  if (state.format !== "todos") parts.push(FORMAT_LABELS[state.format]);
  if (state.audience !== "todos") parts.push(AUDIENCE_LABELS[state.audience]);
  if (state.categories.size) {
    const labels = new Map(categoryCatalog().map(({ id, label }) => [id, label]));
    parts.push([...state.categories].map((id) => labels.get(id) || id).join(" + "));
  }
  if (state.query) parts.push(`“${state.query}”`);
  return parts;
}

function hasActiveFilters() {
  return state.when !== "todos"
    || state.area !== "todos"
    || state.access !== "todos"
    || state.format !== "todos"
    || state.audience !== "todos"
    || state.categories.size > 0
    || Boolean(state.query)
    || Boolean(state.from)
    || Boolean(state.to);
}

function patchResults(filtered) {
  const sorted = sortFilteredEvents(filtered);
  const ids = new Set(sorted.map((event) => String(event?.id || "")).filter(Boolean));
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    const hidden = !ids.has(card.dataset.eventId || "");
    if (card.hidden !== hidden) card.hidden = hidden;
  }
  reorderCards(sorted);

  const dated = patchGroup(dom.datedSection, dom.datedTotal, dom.datedGrid);
  const program = patchGroup(dom.programSection, dom.programTotal, dom.programGrid);
  const flexible = patchGroup(dom.flexibleSection, dom.flexibleTotal, dom.flexibleGrid);
  const total = dated + program + flexible;
  const active = hasActiveFilters();

  setText(dom.total, total);
  setText(dom.agendaKicker, state.query ? "Búsqueda" : active ? "Agenda filtrada" : "Agenda actual");
  setText(dom.agendaTitle, state.query ? "Resultados de búsqueda" : active ? "Resultados" : "Todas las actividades");
  setText(dom.filterSummary, activeFilterParts(total).join(" · "));
  setHidden(dom.clear, !active);
  setHidden(dom.empty, total !== 0);
  setText(dom.emptyCopy, total === 0 ? "Prueba con menos palabras, quita algún filtro o amplía el rango de fechas." : "");
}

function updateDimensionCounts() {
  const matchers = {
    when: eventMatchesWhen,
    area: eventMatchesArea,
    access: eventMatchesAccess,
    format: eventMatchesFormat,
    audience: eventMatchesAudience,
  };
  const containers = {
    when: dom.when,
    area: dom.area,
    access: dom.access,
    format: dom.format,
    audience: dom.audience,
  };
  for (const [dimension, container] of Object.entries(containers)) {
    const matcher = matchers[dimension];
    for (const button of container?.querySelectorAll("[data-filter-value]") || []) {
      const value = button.dataset.filterValue;
      const count = datasetEvents.filter((event) => (
        eventMatches(event, { ignore: [dimension] }) && matcher(event, value)
      )).length;
      setText(button.querySelector("[data-combined-count]"), count);
    }
  }
}

function writeUrl() {
  const url = new URL(window.location.href);
  const setOrDelete = (key, value, defaultValue = "") => {
    if (value && value !== defaultValue) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  };
  setOrDelete("when", state.when, "todos");
  setOrDelete("area", currentCityId() === "valparaiso" ? state.area : "todos", "todos");
  setOrDelete("access", state.access, "todos");
  setOrDelete("format", state.format, "todos");
  setOrDelete("aud", state.audience, "todos");
  setOrDelete("cat", [...state.categories].sort().join(","));
  setOrDelete("q", state.query);
  setOrDelete("from", state.when === "personalizado" ? state.from : "");
  setOrDelete("to", state.when === "personalizado" ? state.to : "");
  url.searchParams.delete("price");
  const next = `${url.pathname}${url.search}${url.hash}`;
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (next !== current) history.replaceState(null, "", next);
}

function readUrl() {
  const params = new URLSearchParams(window.location.search);
  const when = params.get("when") || "todos";
  state.when = Object.hasOwn(WHEN_LABELS, when) ? when : "todos";
  const area = params.get("area") || "todos";
  state.area = currentCityId() === "valparaiso" && Object.hasOwn(AREA_LABELS, area) ? area : "todos";
  const access = params.get("access") || "todos";
  state.access = Object.hasOwn(ACCESS_LABELS, access) ? access : "todos";
  const format = params.get("format") || "todos";
  state.format = Object.hasOwn(FORMAT_LABELS, format) ? format : "todos";
  const audience = params.get("aud") || "todos";
  state.audience = Object.hasOwn(AUDIENCE_LABELS, audience) ? audience : "todos";
  state.categories = new Set((params.get("cat") || "").split(",").map((item) => item.trim()).filter(Boolean));
  state.query = params.get("q") || "";
  state.from = params.get("from") || "";
  state.to = params.get("to") || "";
  if ((state.from || state.to) && !params.has("when")) state.when = "personalizado";
}

function resetFilters() {
  state.when = "todos";
  state.area = "todos";
  state.access = "todos";
  state.format = "todos";
  state.audience = "todos";
  state.categories.clear();
  state.query = "";
  state.from = "";
  state.to = "";
  categoryRenderSignature = "";
  updateControls();
  queueUpdate(true);
}

async function applyFilters({ persist = true } = {}) {
  await loadDataset();
  forceBaseAppFilters();
  const validCategoryIds = new Set(categoryCatalog().map(({ id }) => id));
  state.categories = new Set([...state.categories].filter((id) => validCategoryIds.has(id)));
  if (currentCityId() !== "valparaiso") state.area = "todos";
  updateControls();
  const filtered = datasetEvents.filter((event) => eventMatches(event));
  patchResults(filtered);
  renderCategoryFilters();
  updateDimensionCounts();
  if (persist) writeUrl();
}

async function runQueuedUpdate() {
  updateScheduled = false;
  if (applying || !updatePending) return;
  applying = true;
  const persist = persistPending;
  updatePending = false;
  persistPending = false;
  try {
    await applyFilters({ persist });
  } finally {
    applying = false;
    if (updatePending) queueUpdate(persistPending);
  }
}

function queueUpdate(persist = true) {
  updatePending = true;
  persistPending = persistPending || persist;
  if (updateScheduled || applying) return;
  updateScheduled = true;
  queueMicrotask(runQueuedUpdate);
}

function handleChoice(container, dimension, event) {
  const button = event.target.closest("[data-filter-value]");
  if (!button || !container?.contains(button)) return;
  state[dimension] = button.dataset.filterValue;
  if (dimension === "when" && state.when !== "personalizado") {
    state.from = "";
    state.to = "";
  }
  updateControls();
  queueUpdate(true);
}

dom.when?.addEventListener("click", (event) => handleChoice(dom.when, "when", event));
dom.area?.addEventListener("click", (event) => handleChoice(dom.area, "area", event));
dom.access?.addEventListener("click", (event) => handleChoice(dom.access, "access", event));
dom.format?.addEventListener("click", (event) => handleChoice(dom.format, "format", event));
dom.audience?.addEventListener("click", (event) => handleChoice(dom.audience, "audience", event));

dom.categories?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-combined-category]");
  if (!button) return;
  const id = button.dataset.combinedCategory;
  if (state.categories.has(id)) state.categories.delete(id);
  else state.categories.add(id);
  categoryRenderSignature = "";
  queueUpdate(true);
});

dom.search?.addEventListener("input", () => {
  state.query = dom.search.value.trim();
  queueUpdate(true);
});

for (const input of [dom.dateFrom, dom.dateTo]) {
  input?.addEventListener("change", () => {
    state.from = dom.dateFrom?.value || "";
    state.to = dom.dateTo?.value || "";
    state.when = "personalizado";
    updateControls();
    queueUpdate(true);
  });
}

dom.clear?.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopImmediatePropagation();
  resetFilters();
}, true);

if (dom.discovery) {
  new MutationObserver(() => {
    if (!dom.discovery.hidden) queueUpdate(false);
  }).observe(dom.discovery, { attributes: true, attributeFilter: ["hidden"] });
}

new MutationObserver(() => {
  loadedCity = null;
  categoryRenderSignature = "";
  state.area = "todos";
  queueUpdate(true);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

window.addEventListener("popstate", () => {
  readUrl();
  categoryRenderSignature = "";
  updateControls();
  queueUpdate(false);
});

readUrl();
updateControls();
queueUpdate(false);
