import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { groupedScheduleLabel } from "./public-presentation-rules.mjs?v=20260818-presentation4";
import { eventForCityPresentation, venueHoursForCity } from "./city-presentation-adapter.mjs?v=20260820-cityui1";
import {
  EXHIBITION_GROUP_MIN,
  groupStandaloneExhibitions,
  publicExhibitionCategoryId,
} from "./exhibition-group-core.mjs?v=20260820-groups1";

const REGISTRY = await loadCityRegistry();
const CITIES = REGISTRY.byId;
const EXHIBITION_ID = "exposiciones";
const FALLBACK_IMAGE = new URL("../assets/categoria-exposiciones.jpg", import.meta.url).href;
const grid = document.querySelector("[data-dated-grid]");

let indexedCity = null;
let indexedRevision = 0;
let eventsById = new Map();
let buildTimer = null;
let building = false;

function installStyles() {
  for (const [id, href] of [
    ["unified-exhibition-gallery-styles", "./exhibition-gallery.css?v=20260818-gallery2"],
    ["unified-exhibition-compact-styles", "./exhibition-compact.css?v=20260818-compact8"],
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

function currentConfig() {
  return CITIES[currentCityId()] || null;
}

function syncRuntimeIndex() {
  const cityId = currentCityId();
  if (!cityId) return false;
  const snapshot = getAgendaRuntimeSnapshot(cityId);
  if (!snapshot) return false;
  if (indexedCity === cityId && indexedRevision === snapshot.revision && eventsById.size) return true;
  indexedCity = cityId;
  indexedRevision = snapshot.revision;
  eventsById = new Map(snapshot.events
    .map((event) => {
      const presented = eventForCityPresentation(event, cityId);
      return [String(presented?.id || "").trim(), presented];
    })
    .filter(([id]) => id));
  return eventsById.size > 0;
}

function groupIds(card) {
  return String(card?.dataset?.eventGroup || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
}

function directCards() {
  return [...(grid?.children || [])]
    .filter((node) => node instanceof HTMLElement && node.classList.contains("event-card"));
}

function eventImage(event) {
  const url = String(event?.image?.url || "").trim();
  return /^https?:\/\//i.test(url) ? url : null;
}

function imageElement(url, alt = "") {
  const img = document.createElement("img");
  img.src = url || FALLBACK_IMAGE;
  img.alt = alt;
  img.loading = "lazy";
  img.decoding = "async";
  if (url) img.addEventListener("error", () => { img.src = FALLBACK_IMAGE; }, { once: true });
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
    tile.append(imageElement(url, index === 0 ? "Imágenes de las exposiciones del recinto" : ""));
    collage.append(tile);
  });
  return collage;
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

function buildRow(event, config) {
  const row = document.createElement("article");
  row.className = "grouped-exhibition-item";
  row.dataset.groupedEventId = String(event?.id || "");

  const media = document.createElement("div");
  media.className = "grouped-exhibition-media";
  media.append(imageElement(eventImage(event)));

  const copy = document.createElement("div");
  copy.className = "grouped-exhibition-copy";
  const title = document.createElement("strong");
  title.textContent = event?.title || "Exposición sin título";
  const schedule = document.createElement("small");
  schedule.textContent = groupedScheduleLabel(event, {
    locale: config?.locale || "es",
    timezone: config?.timezone || "UTC",
  });
  copy.append(title, schedule);

  const venue = String(event?.location?.venue || "").trim();
  const city = String(event?.location?.city || "").trim();
  if (venue || city) {
    const location = document.createElement("small");
    location.className = "grouped-exhibition-location";
    location.textContent = [venue, city].filter(Boolean).join(" · ");
    copy.append(location);
  }

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

function commonVenueHours(events, cityId) {
  const values = new Set(events
    .map((event) => venueHoursForCity(event, cityId))
    .map((value) => String(value || "").replace(/\s+/g, " ").trim())
    .filter(Boolean));
  return values.size === 1 ? [...values][0] : null;
}

function sortEvents(events, config) {
  return [...events].sort((a, b) => {
    const aStart = String(a?.schedule?.start || a?.schedule?.occurrences?.[0]?.start || "9999");
    const bStart = String(b?.schedule?.start || b?.schedule?.occurrences?.[0]?.start || "9999");
    return aStart.localeCompare(bStart)
      || String(a?.title || "").localeCompare(String(b?.title || ""), config?.locale || "es");
  });
}

function applyInitialVisibility(card, visibleIds) {
  const ids = groupIds(card);
  const visible = visibleIds instanceof Set ? visibleIds : new Set(ids);
  card.hidden = visible.size === 0;
  for (const row of card.querySelectorAll("[data-grouped-event-id]")) {
    row.hidden = !visible.has(String(row.dataset.groupedEventId || ""));
  }
  const count = card.querySelector("[data-exhibition-visible-count]");
  if (count) count.textContent = `${visible.size} ${visible.size === 1 ? "exposición disponible" : "exposiciones disponibles"}`;
  const summary = card.querySelector("[data-exhibition-summary]");
  if (summary) summary.textContent = `Ver ${visible.size} ${visible.size === 1 ? "exposición" : "exposiciones"}`;
}

function visibleIdsFromExistingGroup(card, ids) {
  if (card.hidden) return new Set();
  const rows = [...card.querySelectorAll("[data-grouped-event-id]")];
  if (!rows.length) return new Set(ids);
  return new Set(rows
    .filter((row) => !row.hidden)
    .map((row) => String(row.dataset.groupedEventId || ""))
    .filter(Boolean));
}

function buildGroupCard(events, visibleIds = null) {
  const cityId = currentCityId();
  const config = currentConfig();
  const sorted = sortEvents(events, config);
  const first = sorted[0];
  const venue = String(first?.location?.venue || "Espacio cultural").trim() || "Espacio cultural";
  const city = String(first?.location?.city || "").trim();
  const ids = sorted.map((event) => String(event?.id || "").trim()).filter(Boolean);

  const card = document.createElement("article");
  card.className = "event-card event-card--dated exhibition-group-card exhibition-venue-card";
  card.dataset.eventGroup = ids.join(",");
  card.dataset.category = EXHIBITION_ID;
  card.dataset.unifiedExhibitionGroup = "true";
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
  const hours = commonVenueHours(sorted, cityId);
  if (hours) {
    const hoursNode = document.createElement("p");
    hoursNode.className = "venue-opening-hours exhibition-venue-hours";
    hoursNode.dataset.exhibitionOpeningHours = "";
    hoursNode.textContent = `Horario del recinto: ${hours}`;
    facts.append(hoursNode);
  }
  if (city) {
    const cityNode = document.createElement("p");
    cityNode.className = "exhibition-venue-city";
    cityNode.textContent = city;
    facts.append(cityNode);
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
  applyInitialVisibility(card, visibleIds ?? new Set(ids));
  return card;
}

function firstNode(nodes) {
  return nodes.reduce((best, node) => {
    if (!best) return node;
    const relation = best.compareDocumentPosition(node);
    return relation & Node.DOCUMENT_POSITION_PRECEDING ? node : best;
  }, null);
}

function replaceCoreGroups() {
  for (const card of directCards()) {
    if (!card.dataset.eventGroup || card.dataset.unifiedExhibitionGroup === "true") continue;
    const ids = groupIds(card);
    const events = ids.map((id) => eventsById.get(id)).filter(Boolean);
    if (events.length < EXHIBITION_GROUP_MIN || events.some((event) => publicExhibitionCategoryId(event) !== EXHIBITION_ID)) continue;
    const replacement = buildGroupCard(events, visibleIdsFromExistingGroup(card, ids));
    card.replaceWith(replacement);
  }
}

function groupStandaloneCards() {
  const nodeById = new Map();
  const events = [];
  for (const card of directCards()) {
    const id = String(card.dataset.eventId || "").trim();
    if (!id) continue;
    const event = eventsById.get(id);
    if (!event || publicExhibitionCategoryId(event) !== EXHIBITION_ID) continue;
    nodeById.set(id, card);
    events.push(event);
  }

  const config = currentConfig();
  const groups = groupStandaloneExhibitions(events, {
    timezone: config?.timezone || "UTC",
    minSize: EXHIBITION_GROUP_MIN,
  });

  for (const group of groups) {
    const nodes = group.events
      .map((event) => nodeById.get(String(event?.id || "")))
      .filter((node) => node?.isConnected && node.parentElement === grid);
    if (nodes.length < EXHIBITION_GROUP_MIN) continue;
    const visibleIds = new Set(group.events
      .map((event) => String(event?.id || ""))
      .filter((id) => id && nodeById.get(id) && !nodeById.get(id).hidden));
    const anchor = firstNode(nodes);
    const replacement = buildGroupCard(group.events, visibleIds);
    grid.insertBefore(replacement, anchor);
    nodes.forEach((node) => node.remove());
  }
}

function refreshCombinedFilters() {
  // combined-filters.js is the single authority for filtered visibility. After
  // replacing individual cards with one group card, request one normal filter
  // pass instead of maintaining a second, competing visibility state here.
  const search = document.querySelector("[data-smart-search]");
  if (search) search.dispatchEvent(new Event("input", { bubbles: true }));
}

function buildGroups() {
  buildTimer = null;
  if (!grid || building || !syncRuntimeIndex()) return;
  building = true;
  try {
    replaceCoreGroups();
    groupStandaloneCards();
    refreshCombinedFilters();
    window.dispatchEvent(new CustomEvent("vivamos:exhibition-groups-rendered", {
      detail: { city: currentCityId(), renderer: "unified" },
    }));
  } finally {
    building = false;
  }
}

function scheduleBuild(delay = 60) {
  if (buildTimer) clearTimeout(buildTimer);
  buildTimer = setTimeout(() => requestAnimationFrame(buildGroups), delay);
}

function resetCity() {
  indexedCity = null;
  indexedRevision = 0;
  eventsById = new Map();
  for (const delay of [80, 320, 900]) setTimeout(() => scheduleBuild(0), delay);
}

installStyles();
for (const eventName of ["vivamos:agenda-data-ready", "vivamos:agenda-rendered", "vivamos:core-ready"]) {
  window.addEventListener(eventName, () => scheduleBuild(20));
}
window.addEventListener("pageshow", () => scheduleBuild(40), { passive: true });

if (grid) new MutationObserver(() => scheduleBuild(40)).observe(grid, { childList: true });
new MutationObserver(resetCity).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-city-option]")) resetCity();
  else if (target.closest("[data-section-filter], [data-category-filter]")) scheduleBuild(30);
}, { passive: true });

document.addEventListener("input", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.matches("[data-search]")) scheduleBuild(30);
}, { passive: true });

scheduleBuild(0);
