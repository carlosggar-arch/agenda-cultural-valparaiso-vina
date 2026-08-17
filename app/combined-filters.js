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
  price: document.querySelector("[data-combined-price]"),
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

const PRICE_LABELS = Object.freeze({
  todos: "Cualquier precio",
  gratis: "Gratis",
  pago: "De pago",
});

const state = {
  when: "todos",
  area: "todos",
  price: "todos",
  categories: new Set(),
  query: "",
  from: "",
  to: "",
};

let datasetEvents = [];
let loadedCity = null;
let updateQueued = false;
let baseResetQueued = false;

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

function eventMatchesPrice(event, price = state.price) {
  if (price === "todos") return true;
  const isFree = event?.price?.is_free;
  if (price === "gratis") return isFree === true;
  if (price === "pago") {
    return isFree === false || Number(event?.price?.min_amount || 0) > 0 || Number(event?.price?.max_amount || 0) > 0;
  }
  return true;
}

function eventMatchesCategories(event, categories = state.categories) {
  if (!categories.size) return true;
  const eventIds = eventCategories(event);
  return [...categories].some((id) => eventIds.has(id));
}

function eventSearchText(event) {
  return normalizeText([
    event?.title,
    ...eventCategories(event).values(),
    event?.location?.venue,
    event?.location?.address,
    event?.location?.city,
    event?.location?.commune,
    event?.description,
    event?.source_name,
    event?.organizer,
    ...(event?.tags || []),
    event?.audience,
    event?.price?.display_text,
    event?.schedule?.display_text,
  ].filter(Boolean).join(" "));
}

function eventMatchesQuery(event, query = state.query) {
  const tokens = normalizeText(query).split(" ").filter(Boolean);
  if (!tokens.length) return true;
  const haystack = eventSearchText(event);
  return tokens.every((token) => haystack.includes(token));
}

function eventMatches(event, options = {}) {
  const ignore = new Set(options.ignore || []);
  if (!ignore.has("when") && !eventMatchesWhen(event)) return false;
  if (!ignore.has("area") && !eventMatchesArea(event)) return false;
  if (!ignore.has("price") && !eventMatchesPrice(event)) return false;
  if (!ignore.has("categories") && !eventMatchesCategories(event)) return false;
  if (!ignore.has("query") && !eventMatchesQuery(event)) return false;
  return true;
}

function forceBaseAppFilters() {
  if (baseResetQueued) return;
  baseResetQueued = true;
  queueMicrotask(() => {
    baseResetQueued = false;
    if (dom.internalSearch && dom.internalSearch.value) {
      dom.internalSearch.value = "";
      dom.internalSearch.dispatchEvent(new Event("input", { bubbles: true }));
    }
    const allSection = dom.internalSections?.querySelector('[data-section-filter="todos"]');
    if (allSection && allSection.getAttribute("aria-pressed") !== "true") allSection.click();
    const allCategory = dom.internalCategories?.querySelector('[data-category-filter=""]');
    if (allCategory && allCategory.getAttribute("aria-pressed") !== "true") allCategory.click();
  });
}

async function loadDataset() {
  const cityId = currentCityId();
  if (loadedCity === cityId && datasetEvents.length) return;
  loadedCity = cityId;
  datasetEvents = [];
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

function renderCategoryFilters() {
  if (!dom.categories) return;
  const catalog = categoryCatalog();
  const contextual = datasetEvents.filter((event) => eventMatches(event, { ignore: ["categories"] }));
  const counts = new Map(catalog.map(({ id }) => [id, 0]));
  for (const event of contextual) {
    for (const id of eventCategories(event).keys()) counts.set(id, (counts.get(id) || 0) + 1);
  }

  dom.categories.replaceChildren();
  for (const category of catalog) {
    const count = counts.get(category.id) || 0;
    const selected = state.categories.has(category.id);
    if (!selected && count === 0) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.combinedCategory = category.id;
    button.className = `category-chip${selected ? " active" : ""}`;
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    button.innerHTML = `<span>${escapeHtml(category.label)}</span><small>${count}</small>`;
    dom.categories.append(button);
  }
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
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

function updateControls() {
  setPressed(dom.when, "[data-filter-value]", state.when);
  setPressed(dom.area, "[data-filter-value]", state.area);
  setPressed(dom.price, "[data-filter-value]", state.price);
  if (dom.search && dom.search.value !== state.query) dom.search.value = state.query;
  if (dom.dateFrom && dom.dateFrom.value !== state.from) dom.dateFrom.value = state.from;
  if (dom.dateTo && dom.dateTo.value !== state.to) dom.dateTo.value = state.to;
  if (dom.customDates) dom.customDates.hidden = state.when !== "personalizado";
  if (dom.areaGroup) dom.areaGroup.hidden = currentCityId() !== "valparaiso";
}

function visibleCards(grid) {
  return [...(grid?.querySelectorAll(".event-card") || [])].filter((card) => !card.hidden);
}

function patchGroup(section, total, grid) {
  const count = visibleCards(grid).length;
  if (total) total.textContent = String(count);
  if (section) section.hidden = count === 0;
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
  if (state.price !== "todos") parts.push(PRICE_LABELS[state.price]);
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
    || state.price !== "todos"
    || state.categories.size > 0
    || Boolean(state.query)
    || Boolean(state.from)
    || Boolean(state.to);
}

function patchResults(filtered) {
  const ids = new Set(filtered.map((event) => String(event?.id || "")).filter(Boolean));
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    card.hidden = !ids.has(card.dataset.eventId || "");
  }

  const dated = patchGroup(dom.datedSection, dom.datedTotal, dom.datedGrid);
  const program = patchGroup(dom.programSection, dom.programTotal, dom.programGrid);
  const flexible = patchGroup(dom.flexibleSection, dom.flexibleTotal, dom.flexibleGrid);
  const total = dated + program + flexible;

  if (dom.total) dom.total.textContent = String(total);
  if (dom.agendaKicker) dom.agendaKicker.textContent = hasActiveFilters() ? "Agenda filtrada" : "Agenda actual";
  if (dom.agendaTitle) dom.agendaTitle.textContent = hasActiveFilters() ? "Resultados" : "Todas las actividades";
  if (dom.filterSummary) dom.filterSummary.textContent = activeFilterParts(total).join(" · ");
  if (dom.clear) dom.clear.hidden = !hasActiveFilters();
  if (dom.empty) dom.empty.hidden = total !== 0;
  if (dom.emptyCopy) dom.emptyCopy.textContent = total === 0
    ? "Prueba a quitar algún filtro o ampliar el rango de fechas."
    : "";
}

function updateDimensionCounts() {
  const update = (container, dimension) => {
    for (const button of container?.querySelectorAll("[data-filter-value]") || []) {
      const value = button.dataset.filterValue;
      const count = datasetEvents.filter((event) => {
        if (!eventMatches(event, { ignore: [dimension] })) return false;
        if (dimension === "when") return eventMatchesWhen(event, value);
        if (dimension === "area") return eventMatchesArea(event, value);
        if (dimension === "price") return eventMatchesPrice(event, value);
        return true;
      }).length;
      const countNode = button.querySelector("[data-combined-count]");
      if (countNode) countNode.textContent = String(count);
    }
  };
  update(dom.when, "when");
  update(dom.area, "area");
  update(dom.price, "price");
}

function writeUrl() {
  const url = new URL(window.location.href);
  const setOrDelete = (key, value, defaultValue = "") => {
    if (value && value !== defaultValue) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  };
  setOrDelete("when", state.when, "todos");
  setOrDelete("area", currentCityId() === "valparaiso" ? state.area : "todos", "todos");
  setOrDelete("price", state.price, "todos");
  setOrDelete("cat", [...state.categories].sort().join(","));
  setOrDelete("q", state.query);
  setOrDelete("from", state.when === "personalizado" ? state.from : "");
  setOrDelete("to", state.when === "personalizado" ? state.to : "");
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function readUrl() {
  const params = new URLSearchParams(window.location.search);
  const when = params.get("when") || "todos";
  state.when = Object.hasOwn(WHEN_LABELS, when) ? when : "todos";
  const area = params.get("area") || "todos";
  state.area = currentCityId() === "valparaiso" && Object.hasOwn(AREA_LABELS, area) ? area : "todos";
  const price = params.get("price") || "todos";
  state.price = Object.hasOwn(PRICE_LABELS, price) ? price : "todos";
  state.categories = new Set((params.get("cat") || "").split(",").map((item) => item.trim()).filter(Boolean));
  state.query = params.get("q") || "";
  state.from = params.get("from") || "";
  state.to = params.get("to") || "";
  if ((state.from || state.to) && !params.has("when")) state.when = "personalizado";
}

function resetFilters() {
  state.when = "todos";
  state.area = "todos";
  state.price = "todos";
  state.categories.clear();
  state.query = "";
  state.from = "";
  state.to = "";
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

function queueUpdate(persist = true) {
  if (updateQueued) return;
  updateQueued = true;
  queueMicrotask(async () => {
    updateQueued = false;
    await applyFilters({ persist });
  });
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
dom.price?.addEventListener("click", (event) => handleChoice(dom.price, "price", event));

dom.categories?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-combined-category]");
  if (!button) return;
  const id = button.dataset.combinedCategory;
  if (state.categories.has(id)) state.categories.delete(id);
  else state.categories.add(id);
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

for (const grid of [dom.datedGrid, dom.programGrid, dom.flexibleGrid]) {
  if (grid) new MutationObserver(() => queueUpdate(false)).observe(grid, { childList: true });
}

if (dom.discovery) {
  new MutationObserver(() => {
    if (!dom.discovery.hidden) {
      forceBaseAppFilters();
      queueUpdate(false);
    }
  }).observe(dom.discovery, { attributes: true, attributeFilter: ["hidden"] });
}

new MutationObserver(() => {
  loadedCity = null;
  state.area = "todos";
  forceBaseAppFilters();
  queueUpdate(true);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

window.addEventListener("popstate", () => {
  readUrl();
  updateControls();
  queueUpdate(false);
});

readUrl();
updateControls();
forceBaseAppFilters();
queueUpdate(false);
