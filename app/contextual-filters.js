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

const categoryContainer = document.querySelector("[data-category-filters]");
const searchInput = document.querySelector("[data-search]");
const sectionFilters = document.querySelector("[data-section-filters]");
const citySwitchLabel = document.querySelector("[data-city-switch-label]");

let datasetEvents = [];
let loadedCity = null;
let updateQueued = false;

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
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
    return occurrences.map((occurrence) => ({ start: occurrence?.start, end: occurrence?.end || occurrence?.start }));
  }
  if (event?.schedule?.start) return [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }];
  return [];
}

function eventDateRanges(event, city) {
  return scheduleWindows(event)
    .map((window) => ({
      start: dateKeyForValue(window.start, city),
      end: dateKeyForValue(window.end, city),
    }))
    .filter((range) => range.start && range.end);
}

function rangesOverlap(range, start, end) {
  return range.start <= end && range.end >= start;
}

function eventMatchesSection(event, sectionId, city) {
  if (!sectionId || sectionId === "todos") return true;
  if (sectionId === "gratis") return event?.price?.is_free === true;

  const today = dateKeyForDate(new Date(), city);
  const ranges = eventDateRanges(event, city);
  if (!ranges.length) return false;

  if (sectionId === "hoy") return ranges.some((range) => rangesOverlap(range, today, today));
  if (sectionId === "fin-de-semana") {
    const weekend = weekendBounds(today);
    return ranges.some((range) => rangesOverlap(range, weekend.start, weekend.end));
  }
  if (sectionId === "terminan-pronto") {
    const limit = addDays(today, 3);
    return ranges.some((range) => range.start <= today && range.end > today && range.end <= limit);
  }
  if (sectionId === "proximos") return ranges.some((range) => range.end >= today);
  return true;
}

function eventMatchesSearch(event, query, locale) {
  if (!query) return true;
  const source = String(event?.source_name || event?.organizer || "");
  const categories = [...eventCategories(event).values()];
  const haystack = [
    event?.title,
    ...categories,
    event?.location?.venue,
    event?.location?.city,
    event?.description,
    source,
    event?.organizer,
  ].filter(Boolean).join(" ").toLocaleLowerCase(locale);
  return haystack.includes(query);
}

function currentSection() {
  return sectionFilters?.querySelector("[data-section-filter].active")?.dataset.sectionFilter
    || sectionFilters?.querySelector('[data-section-filter][aria-pressed="true"]')?.dataset.sectionFilter
    || "todos";
}

function currentCity() {
  const id = document.documentElement.dataset.city;
  return CITY_CONFIG[id] ? id : "valparaiso";
}

async function loadDatasetForCity() {
  const cityId = currentCity();
  if (cityId === loadedCity) return;
  loadedCity = cityId;
  datasetEvents = [];
  const config = CITY_CONFIG[cityId];
  try {
    const response = await fetch(config.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return;
    const dataset = await response.json();
    if (Array.isArray(dataset.events)) datasetEvents = dataset.events;
  } catch {
    datasetEvents = [];
  }
}

function allKnownCategories() {
  const catalog = new Map();
  for (const event of datasetEvents) {
    for (const [id, label] of eventCategories(event)) {
      if (!catalog.has(id)) catalog.set(id, label);
    }
  }
  return catalog;
}

function contextualCounts() {
  const city = CITY_CONFIG[currentCity()];
  const section = currentSection();
  const query = (searchInput?.value || "").trim().toLocaleLowerCase(city.locale);
  const counts = new Map([...allKnownCategories().keys()].map((id) => [id, 0]));

  for (const event of datasetEvents) {
    if (!eventMatchesSection(event, section, city)) continue;
    if (!eventMatchesSearch(event, query, city.locale)) continue;
    for (const id of eventCategories(event).keys()) counts.set(id, (counts.get(id) || 0) + 1);
  }
  return counts;
}

function patchCategoryChips() {
  if (!categoryContainer) return;
  const counts = contextualCounts();
  for (const button of categoryContainer.querySelectorAll("[data-category-filter]")) {
    const id = button.dataset.categoryFilter || "";
    if (!id) {
      button.hidden = true;
      continue;
    }
    button.hidden = false;
    const count = button.querySelector("small");
    const nextCount = String(counts.get(id) || 0);
    if (count && count.textContent !== nextCount) count.textContent = nextCount;
  }
}

function patchCityControl() {
  if (citySwitchLabel && citySwitchLabel.textContent !== "Cambiar ciudad") {
    citySwitchLabel.textContent = "Cambiar ciudad";
  }
}

function ensureVisibleSectionSelection() {
  if (!sectionFilters || sectionFilters.querySelector("[data-section-filter].active")) return;
  const allButton = sectionFilters.querySelector('[data-section-filter="todos"]');
  if (allButton) allButton.click();
}

function queueUpdate() {
  if (updateQueued) return;
  updateQueued = true;
  queueMicrotask(async () => {
    updateQueued = false;
    await loadDatasetForCity();
    patchCityControl();
    ensureVisibleSectionSelection();
    patchCategoryChips();
  });
}

categoryContainer?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category-filter]");
  if (!button || !button.dataset.categoryFilter) return;
  if (button.getAttribute("aria-pressed") !== "true" && !button.classList.contains("active")) return;

  const allButton = categoryContainer.querySelector('[data-category-filter=""]');
  if (!allButton) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  allButton.click();
}, true);

searchInput?.addEventListener("input", queueUpdate);
sectionFilters?.addEventListener("click", queueUpdate);
categoryContainer?.addEventListener("click", queueUpdate);

if (categoryContainer) {
  new MutationObserver(queueUpdate).observe(categoryContainer, { childList: true });
}

new MutationObserver(() => {
  loadedCity = null;
  queueUpdate();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

queueUpdate();
