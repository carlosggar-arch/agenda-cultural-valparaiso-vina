import { CITY_STORAGE_KEY, loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { loadAgendaDataset } from "./data-pipeline.js?v=20260823-pipeline2";
import { renderProgramReferences } from "./program-visibility-policy.js?v=20260819-pipeline1";
import { groupStandaloneExhibitions } from "./exhibition-group-core.mjs?v=20260822-exhibition-quality1";
import { compareAgendaOrder } from "./agenda-order-core.mjs?v=20260822-order1";
import { canonicalPublicCategory } from "./public-category-rules.mjs?v=20260821-shared-taxonomy1";
import { formatSchedule as formatSharedSchedule } from "../assets/event-schedule-display.mjs";
import { eventMatchesCanonicalSection } from "./public-selection-core.mjs?v=20260823-selection1";
import { localDayKey, millisecondsUntilNextLocalDay } from "./local-day-boundary.mjs?v=20260823-day1";

const CITY_REGISTRY = await loadCityRegistry();
const STORAGE_KEY = CITY_STORAGE_KEY;
const CITIES = CITY_REGISTRY.byId;
const DEFAULT_CITY_ID = CITY_REGISTRY.defaultCityId;
const EXHIBITION_CATEGORY_ID = "exposiciones";

let resolveCoreReady;
let coreReadySettled = false;
let dayBoundaryTimer = null;
let materializedDay = null;
let activeReferenceNow = new Date();
let dayRefreshPending = false;

function selectionReferenceNow() {
  return activeReferenceNow instanceof Date && !Number.isNaN(activeReferenceNow.getTime())
    ? activeReferenceNow
    : new Date();
}
export const coreReady = new Promise((resolve) => { resolveCoreReady = resolve; });

function markCoreReady(detail = {}) {
  if (coreReadySettled) return;
  coreReadySettled = true;
  document.documentElement.dataset.vivamosReady = "true";
  window.dispatchEvent(new CustomEvent("vivamos:core-ready", { detail }));
  resolveCoreReady(detail);
}

function scheduleLocalDayRefresh(city) {
  if (dayBoundaryTimer !== null) window.clearTimeout(dayBoundaryTimer);
  materializedDay = localDayKey(new Date(), city.timezone || "UTC");
  dayBoundaryTimer = window.setTimeout(() => {
    dayBoundaryTimer = null;
    if (activeCity?.id === city.id) void refreshActiveCityForDay(city.id);
  }, millisecondsUntilNextLocalDay(new Date(), city.timezone || "UTC"));
}

async function refreshActiveCityForDay(cityId) {
  if (dayRefreshPending || activeCity?.id !== cityId) return;
  dayRefreshPending = true;
  try {
    await loadCity(cityId);
  } finally {
    dayRefreshPending = false;
  }
}

const SECTION_META = Object.freeze({
  hoy: { label: "Hoy", empty: "No hay actividades con fecha para hoy." },
  "fin-de-semana": { label: "Este fin de semana", empty: "No hay actividades fechadas para este fin de semana." },
  proximos: { label: "Próximamente", empty: "No hay próximas actividades fechadas." },
  "terminan-pronto": { label: "Terminan pronto", empty: "No hay actividades en curso que terminen en los próximos días." },
  gratis: { label: "Gratis", empty: "No hay actividades gratuitas con los filtros actuales." },
  "talleres-cursos": { label: "Talleres y cursos", empty: "No hay talleres o cursos con los filtros actuales." },
  todos: { label: "Todas las actividades", empty: "No hay actividades con los filtros actuales." },
});

const dom = {
  chooserBackdrop: document.querySelector("[data-chooser-backdrop]"),
  chooserClose: document.querySelector("[data-chooser-close]"),
  chooserMessage: document.querySelector("[data-chooser-message]"),
  cityOptionsContainer: document.querySelector("[data-city-options]"),
  useLocation: document.querySelector("[data-use-location]"),
  citySwitch: document.querySelector("[data-city-switch]"),
  citySwitchLabel: document.querySelector("[data-city-switch-label]"),
  citySubtitle: document.querySelector("[data-city-subtitle]"),
  heroTitle: document.querySelector("[data-hero-title]"),
  heroCopy: document.querySelector("[data-hero-copy]"),
  status: document.querySelector("[data-status]"),
  discovery: document.querySelector("[data-discovery]"),
  sectionFilters: document.querySelector("[data-section-filters]"),
  sectionButtons: document.querySelectorAll("[data-section-filter]"),
  categoryFilters: document.querySelector("[data-category-filters]"),
  agenda: document.querySelector("[data-agenda]"),
  agendaKicker: document.querySelector("[data-agenda-kicker]"),
  agendaTitle: document.querySelector("[data-agenda-title]"),
  filterSummary: document.querySelector("[data-filter-summary]"),
  filterClear: document.querySelector("[data-filter-clear]"),
  total: document.querySelector("[data-total]"),
  datedSection: document.querySelector("[data-dated-section]"),
  datedTotal: document.querySelector("[data-dated-total]"),
  datedGrid: document.querySelector("[data-dated-grid]"),
  programSection: document.querySelector("[data-program-section]"),
  programTotal: document.querySelector("[data-program-total]"),
  programGrid: document.querySelector("[data-program-grid]"),
  flexibleSection: document.querySelector("[data-flexible-section]"),
  flexibleTotal: document.querySelector("[data-flexible-total]"),
  flexibleGrid: document.querySelector("[data-flexible-grid]"),
  sourcesSection: document.querySelector("[data-sources-section]"),
  sourcesTotal: document.querySelector("[data-sources-total]"),
  sourcesGrid: document.querySelector("[data-sources-grid]"),
  empty: document.querySelector("[data-empty]"),
  emptyCopy: document.querySelector("[data-empty-copy]"),
  searchRow: document.querySelector("[data-search-row]"),
  search: document.querySelector("[data-search]"),
};

let activeCity = null;
let allEvents = [];
let sortedEvents = [];
let secondaryPrograms = [];
let activeSection = "proximos";
let activeCategory = "";
let cachedCategories = [];
let cachedSources = [];
let sourcesRenderGeneration = 0;
let timeContext = null;

const formatterCache = new Map();
let rawCategoryCache = new WeakMap();
let primaryCategoryCache = new WeakMap();
let scheduleWindowCache = new WeakMap();
let dateRangeCache = new WeakMap();
let workshopCache = new WeakMap();
let sortKeyCache = new WeakMap();
let searchHaystackCache = new WeakMap();

function resetEventCaches() {
  rawCategoryCache = new WeakMap();
  primaryCategoryCache = new WeakMap();
  scheduleWindowCache = new WeakMap();
  dateRangeCache = new WeakMap();
  workshopCache = new WeakMap();
  sortKeyCache = new WeakMap();
  searchHaystackCache = new WeakMap();
  sortedEvents = [];
  cachedCategories = [];
  cachedSources = [];
  timeContext = null;
}

function formatterFor(locale, options) {
  const key = `${locale}|${JSON.stringify(options)}`;
  let formatter = formatterCache.get(key);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(locale, options);
    formatterCache.set(key, formatter);
  }
  return formatter;
}

function showChooser(force = false) {
  dom.chooserBackdrop.hidden = false;
  dom.chooserClose.hidden = force;
  dom.chooserMessage.textContent = "";
}

function hideChooser() {
  dom.chooserBackdrop.hidden = true;
}

function setStatus(title, copy) {
  dom.status.hidden = false;
  dom.status.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(copy)}</p>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "cultura";
}

function renderCityOptions() {
  const fragment = document.createDocumentFragment();
  for (const city of CITY_REGISTRY.cities) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = ["city-option", city?.visual?.option_class].filter(Boolean).join(" ");
    button.dataset.cityOption = city.id;

    const symbol = document.createElement("span");
    symbol.className = ["city-symbol", city?.visual?.symbol_class].filter(Boolean).join(" ");
    symbol.setAttribute("aria-hidden", "true");
    const partCount = Math.max(1, Number(city?.visual?.symbol_parts || 1));
    for (let index = 0; index < partCount; index += 1) symbol.append(document.createElement("i"));

    const copy = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = city.label;
    const small = document.createElement("small");
    small.textContent = city.chooser_detail || city.country || "Agenda local";
    copy.append(strong, small);

    const arrow = document.createElement("span");
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";
    button.append(symbol, copy, arrow);
    fragment.append(button);
  }
  dom.cityOptionsContainer?.replaceChildren(fragment);
}

function readSavedCity() {
  try {
    const id = localStorage.getItem(STORAGE_KEY);
    return CITIES[id] ? id : null;
  } catch {
    return null;
  }
}

function saveCity(id) {
  try { localStorage.setItem(STORAGE_KEY, id); } catch {}
}

function dateKeyForDate(date, city) {
  const parts = formatterFor("en-CA", {
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

function formatDateOnly(value, city, withWeekday = false) {
  const key = dateKeyForValue(value, city);
  if (!key) return String(value || "");
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12));
  return formatterFor(city.locale, {
    timeZone: "UTC",
    weekday: withWeekday ? "short" : undefined,
    day: "numeric",
    month: "short",
    year: year !== new Date().getFullYear() ? "numeric" : undefined,
  }).format(date);
}

function formatSchedule(event, city) {
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const end = event?.schedule?.end;
  if (!start) return event?.schedule?.display_text || "Horario por confirmar";

  const startDate = dateKeyForValue(start, city);
  const endDate = end ? dateKeyForValue(end, city) : null;
  if (eventCategoryId(event) === EXHIBITION_CATEGORY_ID && startDate && endDate && startDate !== endDate) {
    const today = currentTimeContext().today;
    if (startDate <= today && endDate >= today) return `En exhibición hasta el ${formatDateOnly(end, city)}`;
    return `${formatDateOnly(start, city)} – ${formatDateOnly(end, city)}`;
  }

  return formatSharedSchedule(event?.schedule, {
    locale: city?.locale || "es-CL",
    timezone: city?.timezone || "America/Santiago",
    now: selectionReferenceNow(),
    referenceDate: currentTimeContext().today,
  });
}

function rawEventCategories(event) {
  const cached = rawCategoryCache.get(event);
  if (cached) return cached;
  const values = [];
  if (event?.primary_category?.id || event?.primary_category?.label) values.push(event.primary_category);
  for (const category of event?.categories || []) values.push(category);
  const unique = new Map();
  for (const category of values) {
    const label = String(category?.label || "").trim();
    const id = String(category?.id || slugify(label)).trim();
    if (label && id && !unique.has(id)) unique.set(id, label);
  }
  rawCategoryCache.set(event, unique);
  return unique;
}

function publicPrimaryCategory(event) {
  const cached = primaryCategoryCache.get(event);
  if (cached) return cached;
  const source = event?.primary_category || event?.categories?.[0] || null;
  const category = canonicalPublicCategory(source)
    || { id: slugify(source?.label || "Actividad cultural"), label: String(source?.label || "Actividad cultural").trim() || "Actividad cultural" };
  primaryCategoryCache.set(event, category);
  return category;
}

function eventCategory(event) {
  return publicPrimaryCategory(event).label;
}

function eventCategoryId(event) {
  return publicPrimaryCategory(event).id;
}

function eventLink(event) {
  const candidate = event?.links?.official || event?.links?.source;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function eventSourceName(event) {
  return String(event?.source_name || event?.organizer || "").trim();
}

function eventSourceUrl(event) {
  const candidate = event?.source_url || event?.links?.source || event?.links?.official;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function contentGroup(event) {
  if (event?.event_type === "program") return "program";
  if (event?.event_type === "flexible_offer") return "flexible";
  return "dated";
}

function typeBadge(event) {
  if (event?.event_type === "program") return "Programa";
  if (event?.event_type === "flexible_offer") return "Actividad disponible";
  if (event?.event_type === "course") return "Curso / taller";
  if (event?.event_type === "workshop") return "Taller";
  return null;
}

function createEventCard(event) {
  const card = document.createElement("article");
  const group = contentGroup(event);
  card.className = `event-card event-card--${group}`;
  card.dataset.eventId = event?.id || "";
  card.dataset.category = eventCategoryId(event);
  const location = [event?.location?.venue, event?.location?.city].filter(Boolean).join(" · ") || "Lugar por confirmar";
  const link = eventLink(event);
  const badge = typeBadge(event);
  card.innerHTML = `
    <div class="card-meta-row">
      <span class="meta">${escapeHtml(eventCategory(event))}</span>
      ${badge ? `<span class="type-badge">${escapeHtml(badge)}</span>` : ""}
    </div>
    <h4>${escapeHtml(event?.title || "Actividad sin título")}</h4>
    <p>${escapeHtml(formatSchedule(event, activeCity))}</p>
    <p>${escapeHtml(location)}</p>
    <div class="event-bottom">
      <span>${event?.price?.is_free === true ? "Gratis" : escapeHtml(event?.price?.display_text || "Precio por confirmar")}</span>
      ${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}
    </div>`;
  return card;
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
  const daysToFriday = weekday === 5 ? 0 : weekday === 6 ? -1 : weekday === 0 ? -2 : 5 - weekday;
  const friday = addDays(todayKey, daysToFriday);
  return { start: friday, end: addDays(friday, 2) };
}

function currentTimeContext() {
  if (timeContext) return timeContext;
  const today = dateKeyForDate(selectionReferenceNow(), activeCity);
  timeContext = { today, weekend: weekendBounds(today), soon: addDays(today, 3) };
  return timeContext;
}

function scheduleWindows(event) {
  const cached = scheduleWindowCache.get(event);
  if (cached) return cached;
  let windows = [];
  if (!["program", "flexible_offer"].includes(event?.event_type)) {
    const occurrences = event?.schedule?.occurrences;
    if (Array.isArray(occurrences) && occurrences.length) {
      windows = occurrences.map((occurrence) => ({ start: occurrence?.start, end: occurrence?.end || occurrence?.start }));
    } else if (event?.schedule?.start) {
      windows = [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }];
    }
  }
  scheduleWindowCache.set(event, windows);
  return windows;
}

function eventDateRanges(event) {
  const cached = dateRangeCache.get(event);
  if (cached) return cached;
  const ranges = scheduleWindows(event)
    .map((window) => ({
      start: dateKeyForValue(window.start, activeCity),
      end: dateKeyForValue(window.end, activeCity),
    }))
    .filter((range) => range.start && range.end);
  dateRangeCache.set(event, ranges);
  return ranges;
}

function rangesOverlap(range, start, end) {
  return range.start <= end && range.end >= start;
}

function isWorkshop(event) {
  if (workshopCache.has(event)) return workshopCache.get(event);
  let result = ["course", "workshop"].includes(event?.event_type);
  if (!result) {
    const text = [...rawEventCategories(event).entries()]
      .flat()
      .join(" ")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLocaleLowerCase("es");
    result = /taller|curso|formacion/.test(text);
  }
  workshopCache.set(event, result);
  return result;
}

function eventMatchesSection(event, sectionId) {
  return eventMatchesCanonicalSection(event, sectionId, activeCity, selectionReferenceNow());
}

function eventMatchesCategory(event, categoryId) {
  if (!categoryId) return true;
  return eventCategoryId(event) === categoryId;
}

function eventSortKey(event) {
  if (sortKeyCache.has(event)) return sortKeyCache.get(event);
  const windows = scheduleWindows(event);
  const candidate = windows[0]?.start || event?.schedule?.start;
  let result = Number.POSITIVE_INFINITY;
  if (candidate) {
    result = /^\d{4}-\d{2}-\d{2}$/.test(String(candidate))
      ? Date.parse(`${candidate}T12:00:00Z`)
      : Date.parse(candidate);
    if (!Number.isFinite(result)) result = Number.POSITIVE_INFINITY;
  }
  sortKeyCache.set(event, result);
  return result;
}

function sortGroupedExhibitionEvents(events) {
  return [...events].sort((a, b) => {
    const dateDiff = eventSortKey(a) - eventSortKey(b);
    if (Number.isFinite(dateDiff) && dateDiff !== 0) return dateDiff;
    return String(a?.title || "").localeCompare(String(b?.title || ""), activeCity?.locale || "es");
  });
}

function sortAgendaEvents(events, now = selectionReferenceNow()) {
  return [...events].sort((a, b) => compareAgendaOrder(a, b, activeCity, now));
}

function createExhibitionGroupCard(events) {
  const sorted = sortGroupedExhibitionEvents(events);
  const first = sorted[0];
  const venue = String(first?.location?.venue || "Espacio cultural").trim();
  const city = String(first?.location?.city || "").trim();
  const card = document.createElement("article");
  card.className = "event-card event-card--dated exhibition-group-card";
  card.dataset.category = EXHIBITION_CATEGORY_ID;
  card.dataset.eventGroup = sorted.map((event) => event?.id || "").filter(Boolean).join(",");

  const items = sorted.map((event) => {
    const link = eventLink(event);
    return `<div class="grouped-exhibition-item">
      <strong>${escapeHtml(event?.title || "Exposición sin título")}</strong>
      <small>${escapeHtml(formatSchedule(event, activeCity))}</small>
      ${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}
    </div>`;
  }).join("");

  card.innerHTML = `
    <div class="card-meta-row"><span class="meta">Exposiciones</span></div>
    <h4>${escapeHtml(venue)}</h4>
    <p><strong>${sorted.length} exposiciones disponibles</strong></p>
    ${city ? `<p>${escapeHtml(city)}</p>` : ""}
    <details class="exhibition-group-details">
      <summary>Ver ${sorted.length} exposiciones</summary>
      <div class="exhibition-group-list">${items}</div>
    </details>`;
  return card;
}

function representativeEventForOrder(events, now) {
  return sortAgendaEvents(events, now)[0] || null;
}

function buildDatedItems(events, now = selectionReferenceNow()) {
  const groups = groupStandaloneExhibitions(events, { timezone: activeCity?.timezone || "UTC" });
  const groupedEvents = new Set();
  const items = [];

  for (const group of groups) {
    group.events.forEach((event) => groupedEvents.add(event));
    items.push({
      type: "group",
      events: group.events,
      representative: representativeEventForOrder(group.events, now),
    });
  }

  for (const event of events) {
    if (!groupedEvents.has(event)) items.push({ type: "event", event, representative: event });
  }

  items.sort((a, b) => {
    if (a.representative && b.representative) return compareAgendaOrder(a.representative, b.representative, activeCity, now);
    if (a.representative) return -1;
    if (b.representative) return 1;
    return 0;
  });
  return items;
}

function renderDatedGroup(grid, section, total, events) {
  total.textContent = String(events.length);
  section.hidden = events.length === 0;
  if (!events.length) {
    grid.replaceChildren();
    return;
  }

  const items = buildDatedItems(events);
  const fragment = document.createDocumentFragment();
  for (const item of items) {
    fragment.append(item.type === "group" ? createExhibitionGroupCard(item.events) : createEventCard(item.event));
  }
  grid.replaceChildren(fragment);
}

function renderGroup(grid, section, total, events) {
  total.textContent = String(events.length);
  section.hidden = events.length === 0;
  const fragment = document.createDocumentFragment();
  for (const event of events) fragment.append(createEventCard(event));
  grid.replaceChildren(fragment);
}

function collectCategoryCounts(events) {
  const categories = new Map();
  for (const event of events) {
    const { id, label } = publicPrimaryCategory(event);
    const current = categories.get(id) || { id, label, count: 0 };
    current.count += 1;
    categories.set(id, current);
  }
  return [...categories.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, activeCity?.locale || "es"));
}

function collectSources(events) {
  const sources = new Map();
  for (const event of events) {
    const name = eventSourceName(event);
    if (!name) continue;
    const key = name.toLocaleLowerCase(activeCity?.locale || "es");
    const current = sources.get(key) || { name, url: null, count: 0, official: false };
    current.count += 1;
    current.official ||= event?.public_status?.source_official === true;
    current.url ||= eventSourceUrl(event);
    sources.set(key, current);
  }
  return [...sources.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, activeCity?.locale || "es"));
}

function prepareStaticMetadata() {
  sortedEvents = sortAgendaEvents(allEvents);
  cachedCategories = collectCategoryCounts(allEvents);
  cachedSources = collectSources(allEvents);
}

function computeSectionCounts(events) {
  const counts = new Map(Object.keys(SECTION_META).map((section) => [section, 0]));
  const { today, weekend, soon } = currentTimeContext();
  for (const event of events) {
    counts.set("todos", counts.get("todos") + 1);
    if (event?.price?.is_free === true) counts.set("gratis", counts.get("gratis") + 1);
    if (isWorkshop(event)) counts.set("talleres-cursos", counts.get("talleres-cursos") + 1);
    const ranges = eventDateRanges(event);
    if (!ranges.length) continue;
    if (ranges.some((range) => rangesOverlap(range, today, today))) counts.set("hoy", counts.get("hoy") + 1);
    if (ranges.some((range) => rangesOverlap(range, weekend.start, weekend.end))) counts.set("fin-de-semana", counts.get("fin-de-semana") + 1);
    if (ranges.some((range) => range.start <= today && range.end > today && range.end <= soon)) counts.set("terminan-pronto", counts.get("terminan-pronto") + 1);
    if (ranges.some((range) => range.end >= today)) counts.set("proximos", counts.get("proximos") + 1);
  }
  return counts;
}

function renderSources() {
  const sources = cachedSources;
  dom.sourcesTotal.textContent = String(sources.length);
  dom.sourcesSection.hidden = sources.length === 0;
  const fragment = document.createDocumentFragment();
  for (const source of sources) {
    const card = document.createElement("article");
    card.className = "source-card";
    const heading = document.createElement("div");
    heading.className = "source-card-heading";
    const name = document.createElement("strong");
    name.textContent = source.name;
    heading.append(name);
    if (source.official) {
      const badge = document.createElement("span");
      badge.className = "source-official-badge";
      badge.textContent = "Oficial";
      heading.append(badge);
    }
    card.append(heading);

    const count = document.createElement("small");
    count.textContent = `${source.count} ${source.count === 1 ? "actividad" : "actividades"} en esta agenda`;
    card.append(count);

    if (source.url) {
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Abrir referencia →";
      card.append(link);
    }
    fragment.append(card);
  }
  dom.sourcesGrid.replaceChildren(fragment);
}

function scheduleSourcesRender() {
  const generation = ++sourcesRenderGeneration;
  const run = () => {
    if (generation !== sourcesRenderGeneration) return;
    renderSources();
  };
  if (typeof requestIdleCallback === "function") requestIdleCallback(run, { timeout: 1200 });
  else requestAnimationFrame(() => setTimeout(run, 0));
}

function renderCategories() {
  const fragment = document.createDocumentFragment();
  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.dataset.categoryFilter = "";
  allButton.className = "category-chip";
  allButton.innerHTML = `<span>Todas</span><small>${allEvents.length}</small>`;
  fragment.append(allButton);

  for (const category of cachedCategories) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.categoryFilter = category.id;
    button.className = "category-chip";
    button.innerHTML = `<span>${escapeHtml(category.label)}</span><small>${category.count}</small>`;
    fragment.append(button);
  }
  dom.categoryFilters.replaceChildren(fragment);
  updateCategoryButtons();
}

function updateCategoryButtons() {
  for (const button of dom.categoryFilters.querySelectorAll("[data-category-filter]")) {
    const active = (button.dataset.categoryFilter || "") === activeCategory;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

function updateSectionCounts(counts) {
  for (const button of dom.sectionButtons) {
    const section = button.dataset.sectionFilter;
    const countNode = button.querySelector("[data-section-count]");
    if (countNode) countNode.textContent = String(counts.get(section) || 0);
    const active = section === activeSection;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

function eventSearchHaystack(event) {
  const cached = searchHaystackCache.get(event);
  if (cached !== undefined) return cached;
  const haystack = [
    event?.title,
    ...rawEventCategories(event).values(),
    eventCategory(event),
    event?.location?.venue,
    event?.location?.city,
    event?.description,
    eventSourceName(event),
    event?.organizer,
    typeBadge(event),
  ].filter(Boolean).join(" ").toLocaleLowerCase(activeCity.locale);
  searchHaystackCache.set(event, haystack);
  return haystack;
}

function currentFilteredEvents() {
  const query = dom.search.value.trim().toLocaleLowerCase(activeCity?.locale || "es");
  return sortedEvents.filter((event) => {
    if (!eventMatchesSection(event, activeSection)) return false;
    if (!eventMatchesCategory(event, activeCategory)) return false;
    return !query || eventSearchHaystack(event).includes(query);
  });
}

function defaultSection(sectionCounts = computeSectionCounts(allEvents)) {
  return (sectionCounts.get("hoy") || 0) > 0 ? "hoy" : "proximos";
}

function updateResultHeading(events, sectionCounts) {
  const meta = SECTION_META[activeSection] || SECTION_META.todos;
  dom.agendaKicker.textContent = activeSection === "hoy" ? "Qué hacer hoy" : "Agenda actual";
  dom.agendaTitle.textContent = meta.label;
  dom.total.textContent = String(events.length);

  const parts = [`${events.length} ${events.length === 1 ? "actividad" : "actividades"}`];
  if (activeCategory) {
    const category = cachedCategories.find((item) => item.id === activeCategory);
    if (category) parts.push(category.label);
  }
  if (dom.search.value.trim()) parts.push(`“${dom.search.value.trim()}”`);
  dom.filterSummary.textContent = parts.join(" · ");
  dom.filterClear.hidden = activeCategory === "" && !dom.search.value.trim() && activeSection === defaultSection(sectionCounts);
  dom.emptyCopy.textContent = meta.empty;
}

function renderEvents() {
  timeContext = null;
  const sectionCounts = computeSectionCounts(allEvents);
  const events = currentFilteredEvents();
  const groups = { dated: [], program: [], flexible: [] };
  for (const event of events) groups[contentGroup(event)].push(event);

  dom.empty.hidden = events.length !== 0;
  renderDatedGroup(dom.datedGrid, dom.datedSection, dom.datedTotal, groups.dated);
  if (groups.program.length) {
    renderGroup(dom.programGrid, dom.programSection, dom.programTotal, groups.program);
  } else {
    renderProgramReferences({ section: dom.programSection, grid: dom.programGrid, total: dom.programTotal }, secondaryPrograms);
  }
  renderGroup(dom.flexibleGrid, dom.flexibleSection, dom.flexibleTotal, groups.flexible);
  updateResultHeading(events, sectionCounts);
  updateSectionCounts(sectionCounts);
  updateCategoryButtons();
}

function resetDiscoveryFilters() {
  timeContext = null;
  activeSection = defaultSection();
  activeCategory = "";
  dom.search.value = "";
  renderEvents();
}

async function loadCity(id) {
  const city = CITIES[id];
  if (!city) return;
  activeCity = city;
  saveCity(id);
  hideChooser();
  sourcesRenderGeneration += 1;

  document.documentElement.lang = city.lang || city.locale || "es";
  document.documentElement.dataset.city = id;
  const theme = document.querySelector('meta[name="theme-color"]');
  if (theme && city.theme_color) theme.setAttribute("content", city.theme_color);
  document.title = `Agenda Cultural · ${city.label}`;
  dom.citySwitchLabel.textContent = city.label;
  dom.citySubtitle.textContent = city.subtitle;
  dom.heroTitle.textContent = `Descubre qué hacer en ${city.label}`;
  dom.heroCopy.textContent = `Agenda local de ${city.label}: explora qué hay hoy, este fin de semana o por categoría.`;
  dom.searchRow.hidden = false;
  dom.search.value = "";
  dom.discovery.hidden = true;
  dom.agenda.hidden = true;
  dom.sourcesSection.hidden = true;
  dom.sourcesGrid.replaceChildren();
  setStatus("Cargando agenda", `Estamos buscando las actividades disponibles en ${city.label}.`);

  try {
    const result = await loadAgendaDataset(city);
    const dataset = result.dataset;
    if (!dataset || !Array.isArray(dataset.events)) throw new Error("Dataset inválido");
    resetEventCaches();
    activeReferenceNow = result.referenceNow instanceof Date ? result.referenceNow : new Date(result.referenceNow || Date.now());
    allEvents = dataset.events;
    secondaryPrograms = result.secondaryPrograms || [];
    prepareStaticMetadata();
    activeCategory = "";
    timeContext = null;
    activeSection = defaultSection();
    dom.discovery.hidden = false;
    dom.agenda.hidden = false;
    dom.status.hidden = true;
    renderCategories();
    renderEvents();
    scheduleLocalDayRefresh(city);
    markCoreReady({ city: id, mode: "full", diagnostics: result.diagnostics || [] });
    scheduleSourcesRender();
  } catch (error) {
    resetEventCaches();
    allEvents = [];
    secondaryPrograms = [];
    prepareStaticMetadata();
    activeCategory = "";
    activeSection = "todos";
    dom.discovery.hidden = true;
    dom.agenda.hidden = false;
    renderCategories();
    renderEvents();
    setStatus("No pudimos cargar la agenda", `La aplicación no pudo leer el dataset de ${city.label}. Intenta nuevamente más tarde.`);
    markCoreReady({ city: id, mode: "error", error: String(error?.message || error) });
  }
}

function haversineKm(a, b) {
  const R = 6371;
  const toRad = (x) => x * Math.PI / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function suggestCityFromCoordinates(lat, lon) {
  const point = { lat, lon };
  const ranked = Object.values(CITIES)
    .map((city) => ({ city, distance: haversineKm(point, city.center) }))
    .sort((a, b) => a.distance - b.distance);
  const nearest = ranked[0];
  return nearest && nearest.distance <= nearest.city.radius_km ? nearest.city.id : null;
}

function useLocation() {
  dom.chooserMessage.textContent = "";
  if (!navigator.geolocation) {
    dom.chooserMessage.textContent = "Este dispositivo no ofrece geolocalización. Elige una ciudad manualmente.";
    return;
  }
  dom.useLocation.disabled = true;
  dom.useLocation.textContent = "Buscando tu ubicación…";
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      dom.useLocation.disabled = false;
      dom.useLocation.innerHTML = '<span aria-hidden="true">◎</span> Usar mi ubicación';
      const id = suggestCityFromCoordinates(coords.latitude, coords.longitude);
      if (id) loadCity(id);
      else dom.chooserMessage.textContent = "No estás cerca de ninguna de las agendas disponibles. Elige una ciudad manualmente.";
    },
    () => {
      dom.useLocation.disabled = false;
      dom.useLocation.innerHTML = '<span aria-hidden="true">◎</span> Usar mi ubicación';
      dom.chooserMessage.textContent = "No pudimos acceder a tu ubicación. Elige una ciudad manualmente.";
    },
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
  );
}

dom.cityOptionsContainer?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-city-option]");
  if (button) loadCity(button.dataset.cityOption);
});
dom.citySwitch.addEventListener("click", () => showChooser(false));
dom.chooserClose.addEventListener("click", hideChooser);
dom.useLocation.addEventListener("click", useLocation);
dom.search.addEventListener("input", renderEvents);
dom.filterClear.addEventListener("click", resetDiscoveryFilters);
dom.sectionFilters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-section-filter]");
  if (!button) return;
  activeSection = button.dataset.sectionFilter;
  renderEvents();
  dom.agenda.scrollIntoView({ behavior: "smooth", block: "start" });
});
dom.categoryFilters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category-filter]");
  if (!button) return;
  activeCategory = button.dataset.categoryFilter || "";
  renderEvents();
  dom.agenda.scrollIntoView({ behavior: "smooth", block: "start" });
});
dom.chooserBackdrop.addEventListener("click", (event) => { if (event.target === dom.chooserBackdrop && activeCity) hideChooser(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && activeCity) hideChooser(); });
window.addEventListener("focus", () => {
  if (!activeCity) return;
  const currentDay = localDayKey(new Date(), activeCity.timezone || "UTC");
  if (materializedDay && currentDay !== materializedDay) void refreshActiveCityForDay(activeCity.id);
});

renderCityOptions();
const requestedCity = new URLSearchParams(window.location.search).get("city");
const initialCity = CITIES[requestedCity] ? requestedCity : readSavedCity();
if (initialCity) loadCity(initialCity);
else if (CITIES[DEFAULT_CITY_ID]) {
  showChooser(true);
  markCoreReady({ mode: "chooser" });
}
