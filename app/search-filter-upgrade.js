const CITY_CONFIG = Object.freeze({
  valparaiso: { dataset: "../agenda_web.json", timezone: "America/Santiago" },
  gijon: { dataset: "./data/gijon/agenda_web.json", timezone: "Europe/Madrid" },
});

const FEATURE_LABELS = Object.freeze({
  family: "Para familias",
  registration: "Con inscripción",
});

const FORMAT_LABELS = Object.freeze({
  todos: "Cualquier modalidad",
  presencial: "Presencial",
  online: "Online",
});

const extraState = {
  format: "todos",
  features: new Set(),
};

let events = [];
let byId = new Map();
let loadedCity = null;
let applyQueued = false;
let suggestionIndex = -1;

const dom = {
  workbench: document.querySelector(".filter-workbench"),
  categoryPanel: document.querySelector(".category-filter-panel"),
  search: document.querySelector("[data-smart-search]"),
  total: document.querySelector("[data-total]"),
  empty: document.querySelector("[data-empty]"),
  clear: document.querySelector("[data-filter-clear]"),
};

function currentCityId() {
  const city = document.documentElement.dataset.city;
  return CITY_CONFIG[city] ? city : "valparaiso";
}

function currentConfig() {
  return CITY_CONFIG[currentCityId()];
}

function normalizeText(value) {
  const text = typeof value === "string" ? value : JSON.stringify(value ?? "");
  return text
    .replace(/<[^>]*>/g, " ")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/\s+/g, " ")
    .trim();
}

function eventCategories(event) {
  const rows = [];
  if (event?.primary_category) rows.push(event.primary_category);
  for (const category of event?.categories || []) rows.push(category);
  return rows
    .map((category) => ({
      id: String(category?.id || "").trim(),
      label: String(category?.label || "").trim(),
    }))
    .filter((category) => category.id || category.label);
}

function eventText(event) {
  return normalizeText([
    event?.title,
    ...eventCategories(event).flatMap((category) => [category.id, category.label]),
    event?.location?.venue,
    event?.location?.address,
    event?.location?.city,
    event?.location?.commune,
    event?.description,
    event?.source_name,
    event?.organizer,
    event?.audience,
    event?.registration_requirements,
    ...(event?.tags || []),
    event?.price?.display_text,
    event?.schedule?.display_text,
  ].filter(Boolean).join(" "));
}

function dateKeyForDate(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: currentConfig().timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function dateKeyForValue(value) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : dateKeyForDate(date);
}

function addDays(dateKey, days) {
  const date = new Date(`${dateKey}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function weekendBounds(todayKey) {
  const weekday = new Date(`${todayKey}T12:00:00Z`).getUTCDay();
  const daysToSaturday = weekday === 6 ? 0 : weekday === 0 ? -1 : 6 - weekday;
  const saturday = addDays(todayKey, daysToSaturday);
  return { start: saturday, end: addDays(saturday, 1) };
}

function eventRanges(event) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  const windows = Array.isArray(occurrences) && occurrences.length
    ? occurrences.map((item) => ({ start: item?.start, end: item?.end || item?.start }))
    : event?.schedule?.start
      ? [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }]
      : [];
  return windows
    .map((range) => ({ start: dateKeyForValue(range.start), end: dateKeyForValue(range.end) }))
    .filter((range) => range.start && range.end);
}

function matchesWhen(event, params) {
  const when = params.get("when") || "todos";
  if (when === "todos") return true;
  const today = dateKeyForDate(new Date());
  let window = null;
  if (when === "hoy") window = { start: today, end: today };
  else if (when === "manana") window = { start: addDays(today, 1), end: addDays(today, 1) };
  else if (when === "fin-de-semana") window = weekendBounds(today);
  else if (when === "7-dias") window = { start: today, end: addDays(today, 6) };
  else if (when === "terminan-pronto") window = { start: today, end: addDays(today, 3), endingSoon: true };
  else if (when === "personalizado") {
    const from = params.get("from") || params.get("to");
    const to = params.get("to") || params.get("from");
    if (from && to) window = from <= to ? { start: from, end: to } : { start: to, end: from };
  }
  if (!window) return false;
  const ranges = eventRanges(event);
  if (window.endingSoon) {
    return ranges.some((range) => range.start <= today && range.end > today && range.end <= window.end);
  }
  return ranges.some((range) => range.start <= window.end && range.end >= window.start);
}

function matchesArea(event, params) {
  if (currentCityId() !== "valparaiso") return true;
  const area = params.get("area") || "todos";
  if (area === "todos") return true;
  const city = normalizeText(event?.location?.city || event?.location?.commune);
  if (area === "valparaiso") return city.includes("valparaiso");
  if (area === "vina") return city.includes("vina del mar") || city === "vina";
  return true;
}

function matchesPrice(event, params) {
  const price = params.get("price") || "todos";
  if (price === "todos") return true;
  const isFree = event?.price?.is_free;
  if (price === "gratis") return isFree === true;
  if (price === "pago") {
    return isFree === false || Number(event?.price?.min_amount || 0) > 0 || Number(event?.price?.max_amount || 0) > 0;
  }
  return true;
}

function matchesCategories(event, params) {
  const selected = (params.get("cat") || "").split(",").filter(Boolean);
  if (!selected.length) return true;
  const ids = new Set(eventCategories(event).map((category) => category.id));
  return selected.some((id) => ids.has(id));
}

function matchesQuery(event, params) {
  const tokens = normalizeText(params.get("q") || "").split(" ").filter(Boolean);
  if (!tokens.length) return true;
  const haystack = eventText(event);
  return tokens.every((token) => haystack.includes(token));
}

function matchesBase(event) {
  const params = new URLSearchParams(window.location.search);
  return matchesWhen(event, params)
    && matchesArea(event, params)
    && matchesPrice(event, params)
    && matchesCategories(event, params)
    && matchesQuery(event, params);
}

function isFamilyEvent(event) {
  const text = eventText(event);
  return [
    "familia", "familiar", "familias", "infantil", "ninos", "ninas", "niñez", "todo publico",
  ].some((marker) => text.includes(normalizeText(marker)));
}

function hasRegistration(event) {
  if (event?.links?.registration) return true;
  if (event?.registration_requirements) return true;
  if (event?.public_status?.registration_open === true) return true;
  const text = eventText(event);
  return ["inscripcion", "inscripciones", "registrate", "registro previo", "cupos limitados", "reserva previa"]
    .some((marker) => text.includes(marker));
}

function matchesFormat(event, format = extraState.format) {
  if (format === "todos") return true;
  const online = event?.location?.online === true;
  if (format === "online") return online;
  if (format === "presencial") return !online;
  return true;
}

function matchesFeatures(event, features = extraState.features) {
  if (features.has("family") && !isFamilyEvent(event)) return false;
  if (features.has("registration") && !hasRegistration(event)) return false;
  return true;
}

function matchesExtra(event, { ignoreFormat = false, ignoreFeature = null } = {}) {
  if (!ignoreFormat && !matchesFormat(event)) return false;
  const features = new Set(extraState.features);
  if (ignoreFeature) features.delete(ignoreFeature);
  return matchesFeatures(event, features);
}

async function loadDataset() {
  const city = currentCityId();
  if (loadedCity === city && events.length) return;
  loadedCity = city;
  events = [];
  byId = new Map();
  try {
    const response = await fetch(CITY_CONFIG[city].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    events = Array.isArray(dataset.events) ? dataset.events : [];
    byId = new Map(events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  } catch {
    events = [];
    byId = new Map();
  }
}

function injectStyles() {
  if (document.querySelector('link[data-search-filter-upgrade-style]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./search-filter-upgrade.css";
  link.dataset.searchFilterUpgradeStyle = "";
  document.head.append(link);
}

function buildAdvancedFilters() {
  if (!dom.workbench || document.querySelector("[data-advanced-filters]")) return;
  const section = document.createElement("section");
  section.className = "advanced-filter-panel";
  section.dataset.advancedFilters = "";
  section.setAttribute("aria-label", "Filtros adicionales");
  section.innerHTML = `
    <div class="advanced-filter-heading">
      <div><h3>Más opciones</h3><p>Afina la agenda por modalidad y características útiles.</p></div>
      <p class="advanced-filter-status" data-extra-status aria-live="polite"></p>
    </div>
    <div class="advanced-filter-grid">
      <fieldset class="filter-group"><legend class="filter-group-title">Modalidad</legend><div class="filter-choice-row" data-extra-format>
        <button class="filter-choice active" type="button" data-extra-format-value="todos" aria-pressed="true">Todas <small data-extra-count>0</small></button>
        <button class="filter-choice" type="button" data-extra-format-value="presencial" aria-pressed="false">Presencial <small data-extra-count>0</small></button>
        <button class="filter-choice" type="button" data-extra-format-value="online" aria-pressed="false">Online <small data-extra-count>0</small></button>
      </div></fieldset>
      <fieldset class="filter-group"><legend class="filter-group-title">Características</legend><div class="filter-choice-row" data-extra-features>
        <button class="filter-choice" type="button" data-extra-feature="family" aria-pressed="false">Para familias <small data-extra-count>0</small></button>
        <button class="filter-choice" type="button" data-extra-feature="registration" aria-pressed="false">Con inscripción <small data-extra-count>0</small></button>
      </div></fieldset>
    </div>`;
  dom.workbench.insertBefore(section, dom.categoryPanel || null);

  section.querySelector("[data-extra-format]")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-extra-format-value]");
    if (!button) return;
    extraState.format = button.dataset.extraFormatValue || "todos";
    writeExtraUrl();
    queueApply();
  });

  section.querySelector("[data-extra-features]")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-extra-feature]");
    const feature = button?.dataset.extraFeature;
    if (!feature) return;
    if (extraState.features.has(feature)) extraState.features.delete(feature);
    else extraState.features.add(feature);
    writeExtraUrl();
    queueApply();
  });
}

function buildSearchAssist() {
  if (!dom.search) return;
  const wrapper = dom.search.closest(".smart-search");
  if (!wrapper || wrapper.querySelector("[data-search-suggestions]")) return;
  dom.search.setAttribute("aria-autocomplete", "list");
  dom.search.setAttribute("aria-controls", "search-suggestions");
  const list = document.createElement("div");
  list.id = "search-suggestions";
  list.className = "search-suggestions";
  list.dataset.searchSuggestions = "";
  list.setAttribute("role", "listbox");
  list.hidden = true;
  wrapper.append(list);
  const help = document.createElement("p");
  help.className = "search-help";
  help.textContent = "Busca por evento, artista, recinto, fuente o categoría. Usa varias palabras para afinar.";
  wrapper.insertAdjacentElement("afterend", help);

  dom.search.addEventListener("input", () => renderSuggestions());
  dom.search.addEventListener("keydown", handleSuggestionKeys);
  dom.search.addEventListener("focus", () => renderSuggestions());
  document.addEventListener("click", (event) => {
    if (!wrapper.contains(event.target)) hideSuggestions();
  });
  list.addEventListener("mousedown", (event) => event.preventDefault());
  list.addEventListener("click", (event) => {
    const option = event.target.closest("[data-suggestion-value]");
    if (!option) return;
    dom.search.value = option.dataset.suggestionValue || "";
    dom.search.dispatchEvent(new Event("input", { bubbles: true }));
    dom.search.focus();
    hideSuggestions();
  });
}

function suggestionCandidates(query) {
  const tokens = normalizeText(query).split(" ").filter(Boolean);
  if (!tokens.length) return [];
  return events
    .map((event) => {
      const title = String(event?.title || "").trim();
      const titleKey = normalizeText(title);
      const haystack = eventText(event);
      if (!tokens.every((token) => haystack.includes(token))) return null;
      let score = 0;
      const queryKey = normalizeText(query);
      if (titleKey === queryKey) score += 100;
      else if (titleKey.startsWith(queryKey)) score += 60;
      else if (titleKey.includes(queryKey)) score += 35;
      score += tokens.filter((token) => titleKey.includes(token)).length * 10;
      if (matchesExtra(event)) score += 5;
      return { event, title, score };
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score || a.title.localeCompare(b.title, "es"))
    .slice(0, 6);
}

function renderSuggestions() {
  const list = document.querySelector("[data-search-suggestions]");
  if (!list || !dom.search) return;
  const query = dom.search.value.trim();
  if (normalizeText(query).length < 2) {
    hideSuggestions();
    return;
  }
  const candidates = suggestionCandidates(query);
  if (!candidates.length) {
    hideSuggestions();
    return;
  }
  list.replaceChildren(...candidates.map(({ event, title }, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.role = "option";
    button.dataset.suggestionValue = title;
    button.dataset.suggestionIndex = String(index);
    const venue = event?.location?.venue || event?.source_name || "";
    const category = event?.primary_category?.label || "";
    button.innerHTML = `<strong>${escapeHtml(title)}</strong><small>${escapeHtml([category, venue].filter(Boolean).join(" · "))}</small>`;
    return button;
  }));
  suggestionIndex = -1;
  list.hidden = false;
  dom.search.setAttribute("aria-expanded", "true");
}

function hideSuggestions() {
  const list = document.querySelector("[data-search-suggestions]");
  if (list) list.hidden = true;
  suggestionIndex = -1;
  dom.search?.setAttribute("aria-expanded", "false");
}

function handleSuggestionKeys(event) {
  const list = document.querySelector("[data-search-suggestions]");
  const options = [...(list?.querySelectorAll("[data-suggestion-value]") || [])];
  if (!options.length || list.hidden) {
    if (event.key === "Escape") hideSuggestions();
    return;
  }
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const delta = event.key === "ArrowDown" ? 1 : -1;
    suggestionIndex = (suggestionIndex + delta + options.length) % options.length;
    options.forEach((option, index) => option.classList.toggle("active", index === suggestionIndex));
    options[suggestionIndex].scrollIntoView({ block: "nearest" });
  } else if (event.key === "Enter" && suggestionIndex >= 0) {
    event.preventDefault();
    options[suggestionIndex].click();
  } else if (event.key === "Escape") {
    hideSuggestions();
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

function readExtraUrl() {
  const params = new URLSearchParams(window.location.search);
  const format = params.get("format") || "todos";
  extraState.format = Object.hasOwn(FORMAT_LABELS, format) ? format : "todos";
  extraState.features = new Set((params.get("features") || "").split(",").filter((item) => FEATURE_LABELS[item]));
}

function writeExtraUrl() {
  const url = new URL(window.location.href);
  if (extraState.format !== "todos") url.searchParams.set("format", extraState.format);
  else url.searchParams.delete("format");
  if (extraState.features.size) url.searchParams.set("features", [...extraState.features].sort().join(","));
  else url.searchParams.delete("features");
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function updateAdvancedControls() {
  const panel = document.querySelector("[data-advanced-filters]");
  for (const button of panel?.querySelectorAll("[data-extra-format-value]") || []) {
    const active = button.dataset.extraFormatValue === extraState.format;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
  for (const button of panel?.querySelectorAll("[data-extra-feature]") || []) {
    const active = extraState.features.has(button.dataset.extraFeature);
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

function updateAdvancedCounts() {
  const panel = document.querySelector("[data-advanced-filters]");
  for (const button of panel?.querySelectorAll("[data-extra-format-value]") || []) {
    const value = button.dataset.extraFormatValue;
    const count = events.filter((event) => matchesBase(event) && matchesFormat(event, value) && matchesFeatures(event)).length;
    const small = button.querySelector("[data-extra-count]");
    if (small) small.textContent = String(count);
  }
  for (const button of panel?.querySelectorAll("[data-extra-feature]") || []) {
    const feature = button.dataset.extraFeature;
    const count = events.filter((event) => {
      if (!matchesBase(event) || !matchesFormat(event)) return false;
      const features = new Set(extraState.features);
      features.add(feature);
      return matchesFeatures(event, features);
    }).length;
    const small = button.querySelector("[data-extra-count]");
    if (small) small.textContent = String(count);
  }
}

function patchSections() {
  const groups = [
    ["[data-dated-section]", "[data-dated-total]", "[data-dated-grid]"],
    ["[data-program-section]", "[data-program-total]", "[data-program-grid]"],
    ["[data-flexible-section]", "[data-flexible-total]", "[data-flexible-grid]"],
  ];
  let total = 0;
  for (const [sectionSelector, totalSelector, gridSelector] of groups) {
    const section = document.querySelector(sectionSelector);
    const totalNode = document.querySelector(totalSelector);
    const grid = document.querySelector(gridSelector);
    const count = [...(grid?.querySelectorAll(".event-card") || [])].filter((card) => !card.hidden).length;
    if (totalNode) totalNode.textContent = String(count);
    if (section) section.hidden = count === 0;
    total += count;
  }
  if (dom.total) dom.total.textContent = String(total);
  if (dom.empty) dom.empty.hidden = total !== 0;
  const status = document.querySelector("[data-extra-status]");
  const labels = [];
  if (extraState.format !== "todos") labels.push(FORMAT_LABELS[extraState.format]);
  labels.push(...[...extraState.features].map((feature) => FEATURE_LABELS[feature]));
  if (status) status.textContent = labels.length ? `${total} resultados · ${labels.join(" · ")}` : "";
  if (dom.clear && labels.length) dom.clear.hidden = false;
}

async function applyAdvancedFilters() {
  applyQueued = false;
  await loadDataset();
  updateAdvancedControls();
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    const event = byId.get(card.dataset.eventId || "");
    if (!event) continue;
    const shouldHide = !(matchesBase(event) && matchesExtra(event));
    if (card.hidden !== shouldHide) card.hidden = shouldHide;
  }
  updateAdvancedCounts();
  patchSections();
}

function queueApply() {
  if (applyQueued) return;
  applyQueued = true;
  queueMicrotask(applyAdvancedFilters);
}

function resetAdvancedFilters() {
  extraState.format = "todos";
  extraState.features.clear();
  writeExtraUrl();
  queueApply();
}

injectStyles();
buildAdvancedFilters();
buildSearchAssist();
readExtraUrl();
updateAdvancedControls();
queueApply();

// The existing combined-filter layer owns date/area/price/category/query state.
// Re-apply this additive layer whenever that layer changes cards or URL state.
const agenda = document.querySelector("[data-agenda]");
if (agenda) {
  new MutationObserver(() => queueApply()).observe(agenda, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["hidden"],
  });
}

new MutationObserver(() => {
  loadedCity = null;
  readExtraUrl();
  queueApply();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

window.addEventListener("popstate", () => {
  readExtraUrl();
  queueApply();
});

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-filter-clear]")) resetAdvancedFilters();
}, true);
