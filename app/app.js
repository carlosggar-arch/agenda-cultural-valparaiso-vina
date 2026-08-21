import "./startup-stability.js?v=20260819-startup2";
import "./render-lifecycle.js?v=20260819-lifecycle1";

// The core is intentionally a dynamic import: the watchdog above must execute
// even if the core module graph fails to load or evaluate.
const { coreReady } = await import("./app-core.js?v=20260820-exhibitionorder2");

// Content presentation is shared across cities. City-specific modules are data
// adapters or media enrichers only; they do not own exhibition-card structure.
const IMAGE_QUALITY_GUARD = "./image-quality-guard.js?v=20260820-images3";
const OPTIONAL_MODULES = [
  "./temporal-priority.js?v=20260819-temporal3",
  "./exhibition-groups.js?v=20260820-groups1",
  "./registration-reminders.js?v=20260820-registration1",
  "./schedule-display.js?v=20260819-runtime1",
  "./footer-credit.js?v=20260818-footer3",
  "./community-source.js?v=20260818-feedback3",
  "./participation-footer.js?v=20260819-feedback7",
];

// Only genuinely city-specific behavior is deferred for Gijón. Exhibition
// grouping, subcards, scrolling and schedule presentation use the same modules
// as Valparaíso/Viña and every future city.
const GIJON_DEFERRED_MODULES = new Set([
  "./temporal-priority.js?v=20260819-temporal3",
]);
const IS_GIJON = String(document.documentElement.dataset.city || "") === "gijon";
if (IS_GIJON) {
  for (let index = OPTIONAL_MODULES.length - 1; index >= 0; index -= 1) {
    if (GIJON_DEFERRED_MODULES.has(OPTIONAL_MODULES[index])) OPTIONAL_MODULES.splice(index, 1);
  }
  OPTIONAL_MODULES.push("./gijon-card-images.js?v=20260820-images2");
  document.documentElement.dataset.gijonStableRuntime = "true";
} else {
  // These enrichers are currently Valpo/Viña specific, but the exhibition
  // renderer itself above is common and consumes the shared runtime snapshot.
  OPTIONAL_MODULES.push(
    "./card-experience.js?v=20260819-runtime1",
    "./card-image-fallback.js?v=20260819-runtime1",
    "./public-presentation-guard.js?v=20260820-text1",
    "./exhibition-hours.js?v=20260820-hours5",
  );
}

function ensureSourcesFallbackLink() {
  const footer = document.querySelector("body > footer");
  if (!footer) return null;
  const dynamic = footer.querySelector("[data-sources-toggle]");
  if (dynamic) return dynamic;

  let fallback = footer.querySelector("[data-sources-fallback]");
  if (!fallback) {
    fallback = document.createElement("a");
    fallback.href = "../fuentes.html";
    fallback.className = "sources-toggle sources-fallback";
    fallback.dataset.sourcesFallback = "";
    fallback.textContent = "Fuentes";
    fallback.setAttribute("aria-label", "Ver todas las fuentes de la agenda");
    const version = footer.querySelector("[data-app-version]");
    if (version) footer.insertBefore(fallback, version);
    else footer.append(fallback);
  }
  footer.classList.add("vivamos-footer--with-sources");
  return fallback;
}

function placeSourcesButtonInFooter() {
  const footer = document.querySelector("body > footer");
  const button = footer?.querySelector("[data-sources-toggle]");
  if (!footer || !button) return false;

  footer.querySelector("[data-sources-fallback]")?.remove();
  const version = footer.querySelector("[data-app-version]");
  if (version && button.nextElementSibling !== version) footer.insertBefore(button, version);
  footer.classList.add("vivamos-footer--with-sources");

  const styleId = "vivamos-footer-sources-layout";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .vivamos-footer.vivamos-footer--with-sources {
        grid-template-columns: auto minmax(0, 1fr) auto auto auto;
      }
      .vivamos-footer .sources-toggle {
        display:inline-flex;
        align-items:center;
        justify-content:center;
        min-height:2.35rem;
        padding:.5rem .85rem;
        border:1px solid rgba(255,255,255,.72);
        border-radius:999px;
        background:#fff;
        color:#174f46;
        font:inherit;
        font-weight:850;
        line-height:1;
        text-decoration:none;
        cursor:pointer;
      }
      .vivamos-footer .sources-toggle:hover,
      .vivamos-footer .sources-toggle:focus-visible {
        border-color:#f4d16d;
        background:#f4d16d;
        color:#103c36;
        outline:2px solid rgba(255,255,255,.72);
        outline-offset:2px;
      }
      @media (max-width: 900px) {
        .vivamos-footer.vivamos-footer--with-sources {
          grid-template-columns: 1fr auto;
        }
        .vivamos-footer.vivamos-footer--with-sources .sources-toggle {
          grid-column: 1;
          width: max-content;
        }
      }
    `;
    document.head.append(style);
  }
  return true;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loadImageQualityGuard() {
  if (IS_GIJON) return;
  const delays = [0, 250, 1000];
  let lastError = null;
  for (const delay of delays) {
    if (delay) await wait(delay);
    try {
      await import(IMAGE_QUALITY_GUARD);
      document.documentElement.dataset.imageQualityGuard = "ready";
      return;
    } catch (error) {
      lastError = error;
    }
  }
  document.documentElement.dataset.imageQualityGuard = "failed";
  console.warn("¡Vivamos!: no se pudo cargar la protección de imágenes tras varios intentos", lastError);
}

async function loadOptionalEnhancements() {
  if (!IS_GIJON) void loadImageQualityGuard();

  const results = await Promise.allSettled(OPTIONAL_MODULES.map((module) => import(module)));
  results.forEach((result, index) => {
    if (result.status === "rejected") console.warn(`¡Vivamos!: mejora opcional omitida (${OPTIONAL_MODULES[index]})`, result.reason);
  });

  // The public source catalogue must always be reachable. Install a normal
  // link first; if the richer in-page source toggle loads successfully, it
  // replaces this fallback. This avoids losing Fuentes because of an optional
  // module failure, missing source section, cache mismatch or footer timing.
  ensureSourcesFallbackLink();
  try {
    await import("./sources-toggle.js?v=20260820-sources2");
  } catch (error) {
    console.warn("¡Vivamos!: vista integrada de fuentes omitida; se conserva el enlace de catálogo", error);
  }
  if (!placeSourcesButtonInFooter()) ensureSourcesFallbackLink();
}

function runWhenMainThreadIsIdle(callback) {
  const run = () => {
    try {
      callback();
    } catch (error) {
      console.warn("¡Vivamos!: mejora diferida omitida", error);
    }
  };
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(run, { timeout: 1200 });
  } else {
    window.setTimeout(run, 120);
  }
}

await coreReady;
// Do not make the just-rendered page compete with optional enrichers. On mobile
// this gives the browser a paint/input opportunity before loading the secondary
// presentation modules.
runWhenMainThreadIsIdle(() => { void loadOptionalEnhancements(); });

const { getAgendaRuntimeSnapshot } = await import("./agenda-runtime-state.mjs?v=20260819-runtime1");
const LONG_EXHIBITION_DAYS = 7;
let exhibitionOrderQueued = false;
const orderingDateFormatters = new Map();

function orderingDateFormatter(city) {
  const timezone = String(city?.timezone || "UTC");
  let formatter = orderingDateFormatters.get(timezone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    orderingDateFormatters.set(timezone, formatter);
  }
  return formatter;
}

function orderingDateKey(value, city) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  if (Number.isNaN(date.getTime()) || !city?.timezone) return null;
  const parts = orderingDateFormatter(city).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function orderingScheduleWindows(event) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.length) {
    return occurrences.map((occurrence) => ({ start: occurrence?.start, end: occurrence?.end || occurrence?.start }));
  }
  if (event?.schedule?.start) return [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }];
  return [];
}

function orderingRanges(event, city) {
  return orderingScheduleWindows(event)
    .map((window) => ({ start: orderingDateKey(window.start, city), end: orderingDateKey(window.end, city) }))
    .filter((range) => range.start && range.end);
}

function orderingEventCategoryId(event) {
  const source = event?.primary_category || event?.categories?.[0] || null;
  const label = String(source?.label || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
  const id = String(source?.id || "").trim();
  if (id === "museos" || id === "exposiciones" || /\bmuseos?\b|\bexposiciones?\b/.test(label)) return "exposiciones";
  return id;
}

function orderingIsLongExhibition(event, city) {
  if (orderingEventCategoryId(event) !== "exposiciones") return false;
  const ranges = orderingRanges(event, city);
  if (!ranges.length) return false;
  const start = ranges.reduce((value, range) => value < range.start ? value : range.start, ranges[0].start);
  const end = ranges.reduce((value, range) => value > range.end ? value : range.end, ranges[0].end);
  const startTime = Date.parse(`${start}T12:00:00Z`);
  const endTime = Date.parse(`${end}T12:00:00Z`);
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) return false;
  return (endTime - startTime) / 86400000 > LONG_EXHIBITION_DAYS;
}

function orderingEventSortKey(event) {
  const candidate = orderingScheduleWindows(event)[0]?.start || event?.schedule?.start;
  if (!candidate) return Number.POSITIVE_INFINITY;
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(candidate))) return Date.parse(`${candidate}T12:00:00Z`);
  const value = Date.parse(candidate);
  return Number.isFinite(value) ? value : Number.POSITIVE_INFINITY;
}

function orderingCardEventIds(card, { visibleOnly = false } = {}) {
  const allIds = card.dataset.eventGroup
    ? String(card.dataset.eventGroup).split(",").map((id) => id.trim()).filter(Boolean)
    : [String(card.dataset.eventId || "").trim()].filter(Boolean);
  if (!visibleOnly || !card.dataset.eventGroup) return allIds;

  const visibleIds = [...card.querySelectorAll("[data-grouped-event-id]")]
    .filter((row) => !row.hidden)
    .map((row) => String(row.dataset.groupedEventId || "").trim())
    .filter(Boolean);
  return visibleIds.length ? visibleIds : allIds;
}

function orderingCardEvents(card, eventsById, options = {}) {
  return orderingCardEventIds(card, options).map((id) => eventsById.get(id)).filter(Boolean);
}

function orderingCardSortKey(card, eventsById) {
  const events = orderingCardEvents(card, eventsById, { visibleOnly: !card.hidden });
  if (!events.length) return Number.POSITIVE_INFINITY;
  return Math.min(...events.map(orderingEventSortKey));
}

function orderingCardIsLongExhibition(card, eventsById, city) {
  const events = orderingCardEvents(card, eventsById, { visibleOnly: !card.hidden });
  return events.length > 0 && events.every((event) => orderingIsLongExhibition(event, city));
}

function categoryFilterIsActive() {
  return document.querySelectorAll('[data-combined-category-filters] [data-combined-category].active').length > 0;
}

function applyExhibitionOrderPolicy() {
  exhibitionOrderQueued = false;
  const snapshot = getAgendaRuntimeSnapshot();
  const grid = document.querySelector('[data-dated-grid]');
  if (!snapshot?.events?.length || !grid) return;

  const eventsById = new Map(
    snapshot.events
      .map((event) => [String(event?.id || ""), event])
      .filter(([id]) => id),
  );
  const cards = [...grid.children].filter((node) => node.classList?.contains("event-card"));
  if (cards.length < 2) return;

  const deferLongExhibitions = !categoryFilterIsActive();
  const indexed = cards.map((card, index) => ({
    card,
    index,
    order: orderingCardSortKey(card, eventsById),
    deferred: deferLongExhibitions && orderingCardIsLongExhibition(card, eventsById, snapshot.city) ? 1 : 0,
  }));
  indexed.sort((a, b) => a.deferred - b.deferred || a.order - b.order || a.index - b.index);
  if (indexed.every((item, index) => item.card === cards[index])) return;

  const fragment = document.createDocumentFragment();
  for (const item of indexed) fragment.append(item.card);
  grid.append(fragment);
}

function scheduleExhibitionOrder() {
  if (exhibitionOrderQueued) return;
  exhibitionOrderQueued = true;
  // A frame boundary coalesces MutationObserver bursts and lets the freshly
  // rendered UI paint before the secondary ordering pass runs.
  if (typeof window.requestAnimationFrame === "function") {
    window.requestAnimationFrame(applyExhibitionOrderPolicy);
  } else {
    window.setTimeout(applyExhibitionOrderPolicy, 0);
  }
}

const datedGrid = document.querySelector('[data-dated-grid]');
if (datedGrid) {
  new MutationObserver(scheduleExhibitionOrder).observe(datedGrid, { childList: true });
}
const combinedCategories = document.querySelector('[data-combined-category-filters]');
if (combinedCategories) {
  new MutationObserver(scheduleExhibitionOrder).observe(combinedCategories, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "aria-pressed"],
  });
}
const filterSummary = document.querySelector('[data-filter-summary]');
if (filterSummary) {
  new MutationObserver(scheduleExhibitionOrder).observe(filterSummary, {
    childList: true,
    characterData: true,
    subtree: true,
  });
}
window.addEventListener("vivamos:agenda-data-ready", scheduleExhibitionOrder);
scheduleExhibitionOrder();