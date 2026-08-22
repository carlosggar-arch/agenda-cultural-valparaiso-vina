import "./startup-stability.js?v=20260819-startup2";
import "./render-lifecycle.js?v=20260819-lifecycle1";

// The core is intentionally a dynamic import: the watchdog above must execute
// even if the core module graph fails to load or evaluate.
const { coreReady } = await import("./app-core.js?v=20260820-exhibitionorder2");

// Presentation is one shared runtime. A city may contribute data, configuration
// or a presentation adapter, but it must not select a different renderer.
const OPTIONAL_MODULES = [
  "./temporal-priority.js?v=20260821-shared-runtime1",
  "./exhibition-groups.js?v=20260821-single-owner1",
  "./registration-reminders.js?v=20260820-registration1",
  "./schedule-display.js?v=20260821-schedule-next1",
  "./event-card-data-quality.mjs?v=20260821-quality1",
  "./exhibition-hours.js?v=20260821-next-hours1",
  "./card-experience.js?v=20260821-shared-runtime1",
  "./public-presentation-guard.js?v=20260821-shared-runtime1",
  "./image-quality-guard.js?v=20260821-shared-runtime1",
  "./footer-credit.js?v=20260818-footer3",
  "./community-source.js?v=20260818-feedback3",
  "./participation-footer.js?v=20260819-feedback7",
];

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

async function loadOptionalEnhancements() {
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

const { getAgendaRuntimeSnapshot } = await import("./agenda-runtime-state.mjs?v=20260821-temporal4");
const { compareAgendaOrder } = await import("./agenda-order-core.mjs?v=20260822-order1");
const { classifyTemporalEvent } = await import("./temporal-priority-core.mjs?v=20260821-temporal4");
let temporalOrderQueued = false;

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

function orderingCardEvents(card, eventsById) {
  return orderingCardEventIds(card, { visibleOnly: !card.hidden })
    .map((id) => eventsById.get(id))
    .filter(Boolean);
}

function representativeEvent(card, eventsById, city, now) {
  const events = orderingCardEvents(card, eventsById);
  if (!events.length) return null;
  return [...events].sort((a, b) => compareAgendaOrder(a, b, city, now))[0] || null;
}

function annotateCard(card, item, city, now) {
  if (!item) return;
  const state = classifyTemporalEvent(item, city, now);
  if (state?.contentKind) card.dataset.contentKind = state.contentKind;
  else delete card.dataset.contentKind;
  if (state?.bucket) card.dataset.temporalBucket = state.bucket;
  else delete card.dataset.temporalBucket;
}

function orderGrid(grid, eventsById, city, now) {
  if (!grid) return;
  const cards = [...grid.children].filter((node) => node.classList?.contains("event-card"));
  if (!cards.length) return;

  const indexed = cards.map((card, index) => {
    const item = representativeEvent(card, eventsById, city, now);
    annotateCard(card, item, city, now);
    return { card, index, item };
  });

  indexed.sort((left, right) => {
    if (left.item && right.item) {
      const diff = compareAgendaOrder(left.item, right.item, city, now);
      if (diff) return diff;
    } else if (left.item) {
      return -1;
    } else if (right.item) {
      return 1;
    }
    return left.index - right.index;
  });

  if (indexed.every((item, index) => item.card === cards[index])) return;
  const fragment = document.createDocumentFragment();
  for (const item of indexed) fragment.append(item.card);
  grid.append(fragment);
}

function applyTemporalOrderPolicy() {
  temporalOrderQueued = false;
  const snapshot = getAgendaRuntimeSnapshot();
  if (!snapshot?.events?.length || !snapshot?.city) return;

  const eventsById = new Map(
    snapshot.events
      .map((event) => [String(event?.id || ""), event])
      .filter(([id]) => id),
  );
  const now = new Date();
  orderGrid(document.querySelector("[data-dated-grid]"), eventsById, snapshot.city, now);
  orderGrid(document.querySelector("[data-program-grid]"), eventsById, snapshot.city, now);
  orderGrid(document.querySelector("[data-flexible-grid]"), eventsById, snapshot.city, now);
}

function scheduleTemporalOrder() {
  if (temporalOrderQueued) return;
  temporalOrderQueued = true;
  if (typeof window.requestAnimationFrame === "function") {
    window.requestAnimationFrame(applyTemporalOrderPolicy);
  } else {
    window.setTimeout(applyTemporalOrderPolicy, 0);
  }
}

for (const selector of ["[data-dated-grid]", "[data-program-grid]", "[data-flexible-grid]"]) {
  const grid = document.querySelector(selector);
  if (grid) new MutationObserver(scheduleTemporalOrder).observe(grid, { childList: true });
}

const combinedCategories = document.querySelector("[data-combined-category-filters]");
if (combinedCategories) {
  new MutationObserver(scheduleTemporalOrder).observe(combinedCategories, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "aria-pressed"],
  });
}

const filterSummary = document.querySelector("[data-filter-summary]");
if (filterSummary) {
  new MutationObserver(scheduleTemporalOrder).observe(filterSummary, {
    childList: true,
    characterData: true,
    subtree: true,
  });
}

window.addEventListener("vivamos:agenda-data-ready", scheduleTemporalOrder);
scheduleTemporalOrder();
