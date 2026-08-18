import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const registry = await loadCityRegistry();
const CITIES = registry.byId;
const grids = [...document.querySelectorAll(".event-grid")];
const discovery = document.querySelector("[data-discovery]");
const internalSearch = document.querySelector("[data-search]");
const internalSections = document.querySelector("[data-section-filters]");
const internalCategories = document.querySelector("[data-category-filters]");
const smartSearch = document.querySelector("[data-smart-search]");

let cityId = null;
let approvedIds = new Set();
let checkTimer = null;
let loadingToken = 0;
let repairing = false;
let repairAttempts = 0;

function currentCityId() {
  const candidate = String(document.documentElement.dataset.city || "").trim();
  return CITIES[candidate] ? candidate : null;
}

async function loadApprovedIds() {
  const nextCity = currentCityId();
  if (!nextCity) return;
  const token = ++loadingToken;
  cityId = nextCity;
  approvedIds = new Set();
  try {
    const response = await fetch(CITIES[nextCity].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    if (token !== loadingToken || nextCity !== currentCityId() || !Array.isArray(dataset?.events)) return;
    approvedIds = new Set(dataset.events.map((event) => String(event?.id || "").trim()).filter(Boolean));
    repairAttempts = 0;
    scheduleCheck(180);
  } catch {
    approvedIds = new Set();
  }
}

function groupedIds(card) {
  return String(card?.dataset?.eventGroup || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
}

function representations() {
  const map = new Map();
  for (const grid of grids) {
    for (const card of grid.querySelectorAll(".event-card")) {
      const standaloneId = String(card.dataset.eventId || "").trim();
      if (standaloneId) {
        const items = map.get(standaloneId) || [];
        items.push({ card, row: null });
        map.set(standaloneId, items);
      }
      for (const id of groupedIds(card)) {
        const items = map.get(id) || [];
        const row = card.querySelector(`[data-grouped-event-id="${CSS.escape(id)}"]`);
        items.push({ card, row });
        map.set(id, items);
      }
    }
  }
  return map;
}

function hasModernFilters() {
  const params = new URLSearchParams(window.location.search);
  if ((params.get("when") || "todos") !== "todos") return true;
  if ((params.get("area") || "todos") !== "todos") return true;
  if ((params.get("access") || "todos") !== "todos") return true;
  if ((params.get("format") || "todos") !== "todos") return true;
  if ((params.get("aud") || "todos") !== "todos") return true;
  if (String(params.get("cat") || "").trim()) return true;
  if (String(params.get("q") || "").trim()) return true;
  if (String(params.get("from") || "").trim() || String(params.get("to") || "").trim()) return true;
  return false;
}

function representationVisible(item) {
  if (!item?.card?.isConnected || item.card.hidden) return false;
  if (item.row && item.row.hidden) return false;
  return true;
}

function forceCompleteBaseRender() {
  let changed = false;
  if (internalSearch && internalSearch.value) {
    internalSearch.value = "";
    internalSearch.dispatchEvent(new Event("input", { bubbles: true }));
    changed = true;
  }
  const allSection = internalSections?.querySelector('[data-section-filter="todos"]');
  if (allSection && allSection.getAttribute("aria-pressed") !== "true") {
    allSection.click();
    changed = true;
  }
  const allCategory = internalCategories?.querySelector('[data-category-filter=""]');
  if (allCategory && allCategory.getAttribute("aria-pressed") !== "true") {
    allCategory.click();
    changed = true;
  }
  return changed;
}

function reapplyModernFilters() {
  if (!smartSearch) return;
  smartSearch.dispatchEvent(new Event("input", { bubbles: true }));
}

async function repair(reason, ids) {
  if (repairing || repairAttempts >= 3) return;
  repairing = true;
  repairAttempts += 1;
  document.documentElement.dataset.eventIntegrityRepair = String(repairAttempts);
  try {
    forceCompleteBaseRender();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    reapplyModernFilters();
    await new Promise((resolve) => setTimeout(resolve, 220));
  } finally {
    repairing = false;
  }
  console.warn(`¡Vivamos!: repaired ${reason}`, ids);
  scheduleCheck(120);
}

function checkIntegrity() {
  checkTimer = null;
  if (repairing || !approvedIds.size || discovery?.hidden) return;
  if (cityId !== currentCityId()) {
    loadApprovedIds();
    return;
  }

  const map = representations();
  const missing = [...approvedIds].filter((id) => !map.has(id));
  if (missing.length) {
    repair("missing approved event representations", missing);
    return;
  }

  if (!hasModernFilters()) {
    const hiddenWithoutFilter = [...approvedIds].filter((id) => !(map.get(id) || []).some(representationVisible));
    if (hiddenWithoutFilter.length) {
      repair("approved events hidden without active filters", hiddenWithoutFilter);
      return;
    }
  }

  repairAttempts = 0;
  delete document.documentElement.dataset.eventIntegrityRepair;
  document.documentElement.dataset.eventIntegrity = "ok";
}

function scheduleCheck(delay = 260) {
  if (checkTimer) clearTimeout(checkTimer);
  checkTimer = setTimeout(checkIntegrity, delay);
}

for (const grid of grids) {
  new MutationObserver(() => scheduleCheck()).observe(grid, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["hidden", "data-event-group", "data-event-id"],
  });
}

if (discovery) {
  new MutationObserver(() => {
    if (!discovery.hidden) scheduleCheck(220);
  }).observe(discovery, { attributes: true, attributeFilter: ["hidden"] });
}

new MutationObserver(() => {
  cityId = null;
  approvedIds = new Set();
  repairAttempts = 0;
  loadApprovedIds();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

window.addEventListener("popstate", () => scheduleCheck(220));
loadApprovedIds();
