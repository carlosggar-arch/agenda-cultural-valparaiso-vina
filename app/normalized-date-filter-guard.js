import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { loadAgendaDataset } from "./data-pipeline.js?v=20260819-pipeline1";

const REGISTRY = await loadCityRegistry();
const datasetCache = new Map();
let runToken = 0;
let timer = null;

const SEARCH_ALIASES = Object.freeze({
  valpo: ["valpo", "valparaiso"],
  valparaiso: ["valparaiso", "valpo"],
  vina: ["vina", "vina del mar"],
  gratis: ["gratis", "gratuito", "gratuita", "liberado", "liberada"],
  gratuito: ["gratis", "gratuito", "gratuita", "liberado", "liberada"],
  inscripcion: ["inscripcion", "registro", "reserva"],
  entradas: ["entradas", "ticket", "tickets"],
  online: ["online", "virtual", "en linea"],
  virtual: ["online", "virtual", "en linea"],
});

function normalizeText(value) {
  return String(value ?? "")
    .replace(/<[^>]*>/g, " ")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/\s+/g, " ")
    .trim();
}

function currentCity() {
  const id = String(document.documentElement.dataset.city || REGISTRY.defaultCityId).trim().toLowerCase();
  return REGISTRY.byId[id] || REGISTRY.byId[REGISTRY.defaultCityId];
}

function pressedValue(selector, fallback = "todos") {
  const button = document.querySelector(`${selector} [data-filter-value][aria-pressed="true"]`)
    || document.querySelector(`${selector} [data-filter-value].active`);
  return String(button?.dataset?.filterValue || fallback).trim() || fallback;
}

function activeWhen() {
  const live = pressedValue("[data-combined-when]", "");
  if (live) return live;
  const params = new URLSearchParams(window.location.search);
  if (params.get("from") || params.get("to")) return params.get("when") || "personalizado";
  return params.get("when") || "todos";
}

function dateKeyForDate(date, city) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: city.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function dateKeyForValue(value, city) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : dateKeyForDate(date, city);
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

function selectedDateWindow(city) {
  const when = activeWhen();
  if (when === "todos") return null;
  const today = dateKeyForDate(new Date(), city);
  if (when === "hoy") return { start: today, end: today };
  if (when === "manana") {
    const tomorrow = addDays(today, 1);
    return { start: tomorrow, end: tomorrow };
  }
  if (when === "fin-de-semana") return weekendBounds(today);
  if (when === "7-dias") return { start: today, end: addDays(today, 6) };
  if (when === "terminan-pronto") return { start: today, end: addDays(today, 3), endingSoon: true };
  if (when === "personalizado") {
    const params = new URLSearchParams(window.location.search);
    const from = String(document.querySelector("[data-date-from]")?.value || params.get("from") || "").trim();
    const to = String(document.querySelector("[data-date-to]")?.value || params.get("to") || "").trim();
    const start = from || to;
    const end = to || from;
    if (!(start && end)) return null;
    return start <= end ? { start, end } : { start: end, end: start };
  }
  return null;
}

function scheduleRanges(event, city) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = Array.isArray(event?.schedule?.occurrences) ? event.schedule.occurrences : [];
  const windows = occurrences.length
    ? occurrences.map((occurrence) => ({ start: occurrence?.start, end: occurrence?.end || occurrence?.start }))
    : event?.schedule?.start
      ? [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }]
      : [];
  return windows.map((window) => ({
    start: dateKeyForValue(window.start, city),
    end: dateKeyForValue(window.end, city),
  })).filter((range) => range.start && range.end);
}

function matchesDate(event, city, window) {
  const ranges = scheduleRanges(event, city);
  if (!ranges.length) return false;
  if (window.endingSoon) {
    return ranges.some((range) => range.start <= window.start && range.end > window.start && range.end <= window.end);
  }
  return ranges.some((range) => range.start <= window.end && range.end >= window.start);
}

function eventCategories(event) {
  const ids = new Set();
  const add = (category) => {
    const id = String(category?.id || "").trim();
    if (id) ids.add(id);
  };
  add(event?.primary_category);
  for (const category of event?.categories || []) add(category);
  return ids;
}

function matchesArea(event, city) {
  const selected = pressedValue("[data-combined-area]");
  if (selected === "todos") return true;
  const rule = (city.areas || []).find((area) => area.id === selected);
  if (!rule) return true;
  const location = normalizeText(event?.location?.city || event?.location?.commune);
  return (rule.match || []).map(normalizeText).filter(Boolean).some((candidate) => location.includes(candidate));
}

function matchesCategories(event) {
  const selected = [...document.querySelectorAll('[data-combined-category-filters] [data-combined-category].active')]
    .map((button) => String(button.dataset.combinedCategory || "").trim())
    .filter(Boolean);
  if (!selected.length) return true;
  const ids = eventCategories(event);
  return selected.some((id) => ids.has(id));
}

function searchText(event) {
  return normalizeText([
    event?.title,
    event?.description,
    event?.location?.venue,
    event?.location?.city,
    event?.location?.commune,
    event?.source_name,
    event?.organizer,
    event?.price?.display_text,
    event?.schedule?.display_text,
    ...(event?.tags || []),
    ...(event?.categories || []).map((category) => category?.label),
    event?.primary_category?.label,
    event?.price?.is_free === true ? "gratis gratuito liberado" : "",
  ].filter(Boolean).join(" "));
}

function matchesQuery(event) {
  const query = normalizeText(document.querySelector("[data-smart-search]")?.value || new URLSearchParams(window.location.search).get("q") || "");
  const tokens = query.split(" ").filter(Boolean);
  if (!tokens.length) return true;
  const haystack = searchText(event);
  return tokens.every((token) => (SEARCH_ALIASES[token] || [token]).some((candidate) => haystack.includes(candidate)));
}

async function normalizedEvents(city) {
  if (!datasetCache.has(city.id)) {
    datasetCache.set(city.id, loadAgendaDataset(city).then((result) => result?.dataset?.events || []));
  }
  return datasetCache.get(city.id);
}

function refreshVisibleCounts() {
  const groups = [
    ["[data-dated-section]", "[data-dated-total]", "[data-dated-grid]"],
    ["[data-program-section]", "[data-program-total]", "[data-program-grid]"],
    ["[data-flexible-section]", "[data-flexible-total]", "[data-flexible-grid]"],
  ];
  let total = 0;
  for (const [sectionSelector, totalSelector, gridSelector] of groups) {
    const section = document.querySelector(sectionSelector);
    const grid = document.querySelector(gridSelector);
    const count = [...(grid?.querySelectorAll(".event-card") || [])].filter((card) => !card.hidden).length;
    const node = document.querySelector(totalSelector);
    if (node && node.textContent !== String(count)) node.textContent = String(count);
    if (section && section.hidden !== (count === 0)) section.hidden = count === 0;
    total += count;
  }
  const totalNode = document.querySelector("[data-total]");
  if (totalNode && totalNode.textContent !== String(total)) totalNode.textContent = String(total);
  const empty = document.querySelector("[data-empty]");
  if (empty && empty.hidden !== (total !== 0)) empty.hidden = total !== 0;
}

async function enforceNormalizedDateVisibility() {
  const token = ++runToken;
  if (document.documentElement.dataset.vivamosSafeMode === "active") return;
  const city = currentCity();
  const window = selectedDateWindow(city);
  if (!window) return;

  let events;
  try {
    events = await normalizedEvents(city);
  } catch (error) {
    console.warn("¡Vivamos!: no se pudo reforzar el filtro de fecha normalizado", error);
    return;
  }
  if (token !== runToken || currentCity().id !== city.id) return;

  const visibleIds = new Set(events
    .filter((event) => matchesDate(event, city, window) && matchesArea(event, city) && matchesCategories(event) && matchesQuery(event))
    .map((event) => String(event?.id || ""))
    .filter(Boolean));

  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    const shouldHide = !visibleIds.has(String(card.dataset.eventId || ""));
    if (card.hidden !== shouldHide) card.hidden = shouldHide;
  }
  refreshVisibleCounts();
  document.documentElement.dataset.normalizedDateFilter = "active";
}

function scheduleEnforcement(delay = 0) {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    void enforceNormalizedDateVisibility();
  }, delay);
}

function afterFilterInteraction() {
  scheduleEnforcement(0);
  setTimeout(() => scheduleEnforcement(0), 120);
}

document.querySelector("[data-combined-when]")?.addEventListener("click", afterFilterInteraction);
for (const input of [document.querySelector("[data-date-from]"), document.querySelector("[data-date-to]")]) {
  input?.addEventListener("change", afterFilterInteraction);
}
document.querySelector("[data-combined-area]")?.addEventListener("click", afterFilterInteraction);
document.querySelector("[data-combined-category-filters]")?.addEventListener("click", afterFilterInteraction);
document.querySelector("[data-smart-search]")?.addEventListener("input", afterFilterInteraction);
window.addEventListener("popstate", afterFilterInteraction);
window.addEventListener("vivamos:core-ready", afterFilterInteraction, { once: true });

let lastCity = currentCity().id;
new MutationObserver(() => {
  const city = currentCity().id;
  if (city === lastCity) return;
  lastCity = city;
  delete document.documentElement.dataset.normalizedDateFilter;
  afterFilterInteraction();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

afterFilterInteraction();