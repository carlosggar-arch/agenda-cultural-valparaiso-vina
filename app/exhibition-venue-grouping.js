import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const CITY_REGISTRY = await loadCityRegistry();
const CITIES = CITY_REGISTRY.byId;
const EXHIBITION_ID = "exposiciones";
const MUSEUM_ID = "museos";
const MIN_GROUP_SIZE = 2;
const grid = document.querySelector("[data-dated-grid]");

let loadedCity = null;
let eventsById = new Map();
let loadToken = 0;
let queued = false;

function currentCityId() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return CITIES[id] ? id : null;
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function publicCategoryId(event) {
  const source = event?.primary_category || event?.categories?.[0] || null;
  const label = String(source?.label || "").trim();
  const id = String(source?.id || slugify(label)).trim();
  if (id === MUSEUM_ID || slugify(label) === MUSEUM_ID) return EXHIBITION_ID;
  return id;
}

function venueKey(event) {
  const venue = String(event?.location?.venue || "").trim();
  if (!venue) return null;
  const city = String(event?.location?.city || "").trim();
  return slugify(`${venue}|${city}`);
}

async function loadDataset() {
  const cityId = currentCityId();
  if (!cityId) return;
  if (loadedCity === cityId && eventsById.size) return;

  const token = ++loadToken;
  loadedCity = cityId;
  eventsById = new Map();

  try {
    const response = await fetch(CITIES[cityId].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    if (token !== loadToken || !Array.isArray(dataset?.events)) return;
    eventsById = new Map(dataset.events.map((event) => [String(event?.id || ""), event]));
  } catch {
    eventsById = new Map();
  }
}

function groupIds(card) {
  return String(card?.dataset?.eventGroup || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
}

function directCards() {
  return [...(grid?.children || [])].filter((node) => node instanceof HTMLElement && node.classList.contains("event-card"));
}

function collectVenueGroups() {
  const groups = new Map();
  const order = new Map(directCards().map((card, index) => [card, index]));

  for (const card of directCards()) {
    if (card.matches(".exhibition-group-card[data-event-group]")) {
      const ids = groupIds(card);
      const events = ids.map((id) => eventsById.get(id)).filter(Boolean);
      const exhibitionEvents = events.filter((event) => publicCategoryId(event) === EXHIBITION_ID);
      if (!exhibitionEvents.length) continue;
      const key = venueKey(exhibitionEvents[0]);
      if (!key) continue;
      const group = groups.get(key) || { ids: new Set(), nodes: new Set(), firstOrder: Number.POSITIVE_INFINITY };
      exhibitionEvents.forEach((event) => group.ids.add(String(event.id)));
      group.nodes.add(card);
      group.firstOrder = Math.min(group.firstOrder, order.get(card) ?? Number.POSITIVE_INFINITY);
      groups.set(key, group);
      continue;
    }

    const id = String(card.dataset.eventId || "").trim();
    if (!id) continue;
    const event = eventsById.get(id);
    if (!event || publicCategoryId(event) !== EXHIBITION_ID) continue;
    const key = venueKey(event);
    if (!key) continue;
    const group = groups.get(key) || { ids: new Set(), nodes: new Set(), firstOrder: Number.POSITIVE_INFINITY };
    group.ids.add(id);
    group.nodes.add(card);
    group.firstOrder = Math.min(group.firstOrder, order.get(card) ?? Number.POSITIVE_INFINITY);
    groups.set(key, group);
  }

  return [...groups.entries()].sort((a, b) => a[1].firstOrder - b[1].firstOrder);
}

function sameIds(card, ids) {
  const current = [...new Set(groupIds(card))].sort();
  const target = [...new Set(ids)].sort();
  return current.length === target.length && current.every((id, index) => id === target[index]);
}

function consolidateVenue(key, group) {
  const ids = [...group.ids];
  if (ids.length < MIN_GROUP_SIZE) return;

  const nodes = [...group.nodes].filter((node) => node.isConnected && node.parentElement === grid);
  if (!nodes.length) return;

  const existingGroups = nodes.filter((node) => node.matches(".exhibition-group-card[data-event-group]"));
  if (nodes.length === 1 && existingGroups.length === 1 && sameIds(existingGroups[0], ids)) return;

  const anchor = document.createElement("article");
  anchor.className = "event-card event-card--dated exhibition-group-card";
  anchor.dataset.eventGroup = ids.join(",");
  anchor.dataset.category = EXHIBITION_ID;
  anchor.dataset.venueExhibitionGroup = key;

  const first = nodes.reduce((best, node) => {
    if (!best) return node;
    const position = best.compareDocumentPosition(node);
    return position & Node.DOCUMENT_POSITION_PRECEDING ? node : best;
  }, null);

  grid.insertBefore(anchor, first);
  nodes.forEach((node) => node.remove());
}

async function consolidate() {
  queued = false;
  if (!grid) return;
  await loadDataset();
  if (!eventsById.size) return;
  for (const [key, group] of collectVenueGroups()) consolidateVenue(key, group);
}

function queueConsolidate() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(consolidate);
}

if (grid) {
  new MutationObserver(queueConsolidate).observe(grid, { childList: true });
}

new MutationObserver(() => {
  loadedCity = null;
  eventsById = new Map();
  queueConsolidate();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

queueConsolidate();
