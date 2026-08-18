import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { groupedScheduleLabel } from "./public-presentation-rules.mjs?v=20260818-presentation4";

const REGISTRY = await loadCityRegistry();
const CITIES = REGISTRY.byId;
const EXHIBITION_ID = "exposiciones";
const MIN_GROUP_SIZE = 2;
const FALLBACK_IMAGE = new URL("../assets/categoria-exposiciones.jpg", import.meta.url).href;
const grid = document.querySelector("[data-dated-grid]");

let loadedCity = null;
let eventsById = new Map();
let buildTimer = null;
let syncTimer = null;
let building = false;

function installStyles() {
  for (const [id, href] of [
    ["static-exhibition-gallery-styles", "./exhibition-gallery.css?v=20260818-gallery2"],
    ["static-exhibition-compact-styles", "./exhibition-compact.css?v=20260818-compact8"],
  ]) {
    if (document.getElementById(id)) continue;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = new URL(href, import.meta.url).href;
    document.head.append(link);
  }
}

function currentCityId() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return CITIES[id] ? id : null;
}

function normalizeKey(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function categoryId(event) {
  return String(event?.primary_category?.id || event?.categories?.[0]?.id || "").trim();
}

function venueKey(event) {
  const venue = String(event?.location?.venue || "").trim();
  if (!venue) return null;
  return normalizeKey(`${venue}|${event?.location?.city || ""}`);
}

function eventImage(event) {
  const url = String(event?.image?.url || "").trim();
  return /^https?:\/\//i.test(url) ? url : null;
}

function eventLink(event) {
  const candidate = event?.links?.official || event?.links?.source;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function priceLabel(event) {
  if (event?.price?.is_free === true) return "Gratis";
  return String(event?.price?.display_text || "").trim();
}

function explicitVenueHours(events) {
  const values = new Set();
  for (const event of events) {
    const schedule = event?.schedule || {};
    const opening = schedule.opening_hours || {};
    const candidates = [
      opening.display_text,
      schedule.venue_opening_hours,
      schedule.visit_hours,
      event?.location?.opening_hours,
    ];
    const value = candidates.map((item) => String(item || "").trim()).find(Boolean);
    if (value) values.add(value);
  }
  return values.size === 1 ? [...values][0] : null;
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

async function loadDataset() {
  const cityId = currentCityId();
  if (!cityId) return false;
  if (loadedCity === cityId && eventsById.size) return true;
  loadedCity = cityId;
  eventsById = new Map();
  try {
    const response = await fetch(CITIES[cityId].dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return false;
    const dataset = await response.json();
    if (currentCityId() !== cityId || !Array.isArray(dataset?.events)) return false;
    eventsById = new Map(dataset.events
      .map((event) => [String(event?.id || "").trim(), event])
      .filter(([id]) => id));
    return eventsById.size > 0;
  } catch {
    return false;
  }
}

function sentinelRoot() {
  let root = document.querySelector("[data-static-exhibition-sentinels]");
  if (root) return root;
  root = document.createElement("div");
  root.dataset.staticExhibitionSentinels = "";
  root.hidden = true;
  root.setAttribute("aria-hidden", "true");
  document.body.append(root);
  return root;
}

function resetSentinels() {
  sentinelRoot().replaceChildren();
}

function ensureSentinel(id) {
  const root = sentinelRoot();
  let node = root.querySelector(`[data-event-id="${CSS.escape(id)}"]`);
  if (node) return node;
  node = document.createElement("span");
  node.className = "event-card static-exhibition-filter-sentinel";
  node.dataset.eventId = id;
  root.append(node);
  return node;
}

function imageElement(url, alt) {
  const img = document.createElement("img");
  img.src = url || FALLBACK_IMAGE;
  img.alt = alt || "";
  img.loading = "lazy";
  img.decoding = "async";
  if (url && url !== FALLBACK_IMAGE) {
    img.addEventListener("error", () => {
      img.src = FALLBACK_IMAGE;
    }, { once: true });
  }
  return img;
}

function buildCollage(events) {
  const collage = document.createElement("div");
  collage.className = "exhibition-collage";
  collage.dataset.exhibitionCollage = "";
  const urls = [];
  for (const event of events) {
    const url = eventImage(event);
    if (url && !urls.includes(url)) urls.push(url);
    if (urls.length >= 4) break;
  }
  if (!urls.length) urls.push(FALLBACK_IMAGE);
  collage.dataset.count = String(urls.length);
  urls.forEach((url, index) => {
    const tile = document.createElement("div");
    tile.className = "exhibition-collage-tile";
    tile.append(imageElement(url, index === 0 ? "Imagen representativa de las exposiciones" : ""));
    collage.append(tile);
  });
  return collage;
}

function buildRow(event, config) {
  const row = document.createElement("article");
  row.className = "grouped-exhibition-item";
  row.dataset.groupedEventId = String(event?.id || "");

  const media = document.createElement("div");
  media.className = "grouped-exhibition-media";
  media.append(imageElement(eventImage(event), ""));

  const copy = document.createElement("div");
  copy.className = "grouped-exhibition-copy";
  const title = document.createElement("strong");
  title.textContent = event?.title || "Exposición sin título";
  const schedule = document.createElement("small");
  schedule.textContent = groupedScheduleLabel(event, { locale: config.locale, timezone: config.timezone });
  copy.append(title, schedule);
  const price = priceLabel(event);
  if (price) {
    const priceNode = document.createElement("span");
    priceNode.className = "grouped-exhibition-price";
    priceNode.textContent = price;
    copy.append(priceNode);
  }

  const actions = document.createElement("div");
  actions.className = "grouped-exhibition-actions";
  const href = eventLink(event);
  if (href) {
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Fuente →";
    actions.append(link);
  }

  row.append(media, copy, actions);
  return row;
}

function buildGroupCard(events) {
  const config = CITIES[currentCityId()];
  const sorted = [...events].sort((a, b) => {
    const aStart = String(a?.schedule?.start || a?.schedule?.occurrences?.[0]?.start || "9999");
    const bStart = String(b?.schedule?.start || b?.schedule?.occurrences?.[0]?.start || "9999");
    return aStart.localeCompare(bStart) || String(a?.title || "").localeCompare(String(b?.title || ""), config.locale || "es");
  });
  const first = sorted[0];
  const venue = String(first?.location?.venue || "Espacio cultural").trim() || "Espacio cultural";
  const city = String(first?.location?.city || "").trim();
  const ids = sorted.map((event) => String(event?.id || "").trim()).filter(Boolean);

  const card = document.createElement("article");
  card.className = "event-card event-card--dated exhibition-group-card exhibition-venue-card";
  card.dataset.eventGroup = ids.join(",");
  card.dataset.category = EXHIBITION_ID;
  card.dataset.staticExhibitionGroup = "true";
  card.append(buildCollage(sorted));

  const body = document.createElement("div");
  body.className = "exhibition-venue-body";
  const meta = document.createElement("div");
  meta.className = "exhibition-venue-meta";
  meta.textContent = "Exposiciones";

  const heading = document.createElement("div");
  heading.className = "exhibition-venue-heading";
  const headingCopy = document.createElement("div");
  const title = document.createElement("h4");
  title.textContent = venue;
  const count = document.createElement("p");
  count.className = "exhibition-venue-count";
  count.dataset.exhibitionVisibleCount = "";
  headingCopy.append(title, count);
  heading.append(headingCopy);

  const facts = document.createElement("div");
  facts.className = "exhibition-venue-facts";
  if (city) {
    const cityNode = document.createElement("p");
    cityNode.className = "exhibition-venue-city";
    cityNode.textContent = city;
    facts.append(cityNode);
  }
  const hours = explicitVenueHours(sorted);
  if (hours) {
    const hoursNode = document.createElement("p");
    hoursNode.className = "venue-opening-hours exhibition-venue-hours";
    hoursNode.textContent = `Horario del recinto: ${hours}`;
    facts.append(hoursNode);
  }

  const details = document.createElement("details");
  details.className = "exhibition-group-details";
  details.open = true;
  const summary = document.createElement("summary");
  summary.dataset.exhibitionSummary = "";
  const list = document.createElement("div");
  list.className = "exhibition-group-list";
  sorted.forEach((event) => list.append(buildRow(event, config)));
  details.append(summary, list);

  body.append(meta, heading, facts, details);
  card.append(body);
  ids.forEach(ensureSentinel);
  return card;
}

function collectBuckets() {
  const buckets = new Map();
  directCards().forEach((node, index) => {
    const ids = node.dataset.eventId ? [String(node.dataset.eventId).trim()] : groupIds(node);
    for (const id of ids) {
      const event = eventsById.get(id);
      if (!event || categoryId(event) !== EXHIBITION_ID) continue;
      const key = venueKey(event);
      if (!key) continue;
      const bucket = buckets.get(key) || { events: new Map(), nodes: new Set(), firstIndex: index };
      bucket.events.set(id, event);
      bucket.nodes.add(node);
      bucket.firstIndex = Math.min(bucket.firstIndex, index);
      buckets.set(key, bucket);
    }
  });
  return [...buckets.values()].sort((a, b) => a.firstIndex - b.firstIndex);
}

function alreadyBuiltForCurrentGrid() {
  return Boolean(grid?.querySelector(':scope > [data-static-exhibition-group="true"]'));
}

async function buildGroups() {
  buildTimer = null;
  if (!grid || building || alreadyBuiltForCurrentGrid()) {
    scheduleSync(0);
    return;
  }
  building = true;
  try {
    if (!(await loadDataset())) return;
    resetSentinels();
    const buckets = collectBuckets().filter((bucket) => bucket.events.size >= MIN_GROUP_SIZE);
    for (const bucket of buckets) {
      const nodes = [...bucket.nodes].filter((node) => node.isConnected && node.parentElement === grid);
      if (!nodes.length) continue;
      const first = nodes.reduce((best, node) => {
        if (!best) return node;
        const relation = best.compareDocumentPosition(node);
        return relation & Node.DOCUMENT_POSITION_PRECEDING ? node : best;
      }, null);
      const card = buildGroupCard([...bucket.events.values()]);
      grid.insertBefore(card, first);
      nodes.forEach((node) => node.remove());
    }
    refreshCombinedFilters();
    scheduleSync(30);
  } finally {
    building = false;
  }
}

function refreshCombinedFilters() {
  const search = document.querySelector("[data-smart-search]");
  if (!search) return;
  search.dispatchEvent(new Event("input", { bubbles: true }));
}

function visibleIdsForGroup(card) {
  return groupIds(card).filter((id) => {
    const sentinel = sentinelRoot().querySelector(`[data-event-id="${CSS.escape(id)}"]`);
    return !sentinel || !sentinel.hidden;
  });
}

function syncGroup(card) {
  const visibleIds = new Set(visibleIdsForGroup(card));
  card.hidden = visibleIds.size === 0;
  for (const row of card.querySelectorAll("[data-grouped-event-id]")) {
    row.hidden = !visibleIds.has(String(row.dataset.groupedEventId || ""));
  }
  const count = card.querySelector("[data-exhibition-visible-count]");
  if (count) count.textContent = `${visibleIds.size} ${visibleIds.size === 1 ? "exposición disponible" : "exposiciones disponibles"}`;
  const summary = card.querySelector("[data-exhibition-summary]");
  if (summary) summary.textContent = `Ver ${visibleIds.size} ${visibleIds.size === 1 ? "exposición" : "exposiciones"}`;
}

function directVisibleCount(targetGrid) {
  if (!targetGrid) return 0;
  let count = 0;
  for (const card of targetGrid.children) {
    if (!(card instanceof HTMLElement) || !card.classList.contains("event-card") || card.hidden) continue;
    if (card.dataset.staticExhibitionGroup === "true") {
      count += visibleIdsForGroup(card).length;
    } else if (card.dataset.eventId) {
      count += 1;
    }
  }
  return count;
}

function syncTotals() {
  const datedGrid = document.querySelector("[data-dated-grid]");
  const programGrid = document.querySelector("[data-program-grid]");
  const flexibleGrid = document.querySelector("[data-flexible-grid]");
  const dated = directVisibleCount(datedGrid);
  const program = directVisibleCount(programGrid);
  const flexible = directVisibleCount(flexibleGrid);
  const total = dated + program + flexible;
  const datedNode = document.querySelector("[data-dated-total]");
  const programNode = document.querySelector("[data-program-total]");
  const flexibleNode = document.querySelector("[data-flexible-total]");
  const totalNode = document.querySelector("[data-total]");
  if (datedNode) datedNode.textContent = String(dated);
  if (programNode) programNode.textContent = String(program);
  if (flexibleNode) flexibleNode.textContent = String(flexible);
  if (totalNode) totalNode.textContent = String(total);
  const summary = document.querySelector("[data-filter-summary]");
  if (summary?.textContent) {
    summary.textContent = summary.textContent.replace(/^\d+\s+actividades?/, `${total} ${total === 1 ? "actividad" : "actividades"}`);
  }
}

function syncAll() {
  syncTimer = null;
  for (const card of grid?.querySelectorAll(':scope > [data-static-exhibition-group="true"]') || []) syncGroup(card);
  syncTotals();
}

function scheduleSync(delay = 0) {
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(() => requestAnimationFrame(syncAll), delay);
}

function scheduleBuild(delay = 80) {
  if (buildTimer) clearTimeout(buildTimer);
  buildTimer = setTimeout(() => requestAnimationFrame(buildGroups), delay);
}

function scheduleCityRebuilds() {
  loadedCity = null;
  eventsById = new Map();
  for (const delay of [180, 650, 1400]) setTimeout(() => scheduleBuild(0), delay);
}

installStyles();
for (const delay of [120, 480, 1100]) setTimeout(() => scheduleBuild(0), delay);
window.addEventListener("pageshow", () => scheduleBuild(80), { passive: true });
window.addEventListener("popstate", () => scheduleSync(20), { passive: true });

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-city-option]")) {
    scheduleCityRebuilds();
    return;
  }
  if (target.closest("[data-section-filter], [data-category-filter], [data-filter-clear]")) {
    scheduleBuild(40);
    return;
  }
  if (target.closest("[data-filter-value], [data-combined-category]")) scheduleSync(20);
}, { passive: true });

document.addEventListener("input", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.matches("[data-search]")) scheduleBuild(40);
  else if (target.matches("[data-smart-search], [data-date-from], [data-date-to]")) scheduleSync(20);
}, { passive: true });

document.addEventListener("change", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.matches("[data-date-from], [data-date-to]")) scheduleSync(20);
}, { passive: true });
