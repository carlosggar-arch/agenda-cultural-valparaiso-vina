import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const CITY_REGISTRY = await loadCityRegistry();
const CITY_CONFIG = CITY_REGISTRY.byId;
const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);
const datedGrid = document.querySelector("[data-dated-grid]");

let loadedCity = null;
let eventsById = new Map();
let loadingToken = 0;

function currentCityId() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return CITY_CONFIG[id] ? id : null;
}

function isExhibition(event) {
  const primaryId = String(event?.primary_category?.id || "").trim();
  if (EXHIBITION_IDS.has(primaryId)) return true;
  return (event?.categories || []).some((category) => EXHIBITION_IDS.has(String(category?.id || "").trim()));
}

function validTime(value) {
  return /^\d{2}:\d{2}$/.test(String(value || "").trim());
}

function explicitVenueHours(event) {
  if (!isExhibition(event)) return null;
  const schedule = event?.schedule || {};
  const openingHours = schedule.opening_hours || {};

  // Venue hours must come from an explicit visit-hours field. Never infer them
  // from schedule.start: that timestamp can be an inauguration, talk or other
  // one-off activity and is not evidence of when the museum opens.
  const opening = String(schedule.opening_time || openingHours.opening_time || "").trim();
  const closing = String(schedule.closing_time || openingHours.closing_time || "").trim();
  if (validTime(opening) && validTime(closing)) return `${opening}–${closing}`;

  const display = String(openingHours.display_text || "").replace(/\s+/g, " ").trim();
  const match = display.match(/\b([01]?\d|2[0-3]):[0-5]\d\s*[–—-]\s*([01]?\d|2[0-3]):[0-5]\d\b/u);
  return match ? match[0].replace(/\s*[–—-]\s*/u, "–") : null;
}

function upsertOpeningParagraph(card, text, beforeNode = null) {
  let node = card.querySelector(":scope > .venue-opening-hours");
  if (!text) {
    node?.remove();
    return;
  }
  if (!node) {
    node = document.createElement("p");
    node.className = "venue-opening-hours";
    if (beforeNode) card.insertBefore(node, beforeNode);
    else card.append(node);
  }
  if (node.textContent !== text) node.textContent = text;
}

function patchStandaloneCard(card) {
  const id = String(card.dataset.eventId || "").trim();
  if (!id) return;
  const event = eventsById.get(id);
  const hours = event ? explicitVenueHours(event) : null;
  const schedule = card.querySelector(":scope > h4 + p");
  const existing = card.querySelector(":scope > .venue-opening-hours");

  if (!hours) {
    existing?.remove();
    return;
  }

  const text = `Horario de visita: ${hours}`;
  if (!existing) {
    const node = document.createElement("p");
    node.className = "venue-opening-hours";
    node.textContent = text;
    schedule?.insertAdjacentElement("afterend", node);
  } else if (existing.textContent !== text) {
    existing.textContent = text;
  }
}

function setGroupedOpeningHours(card, hours) {
  // Group cards are assembled asynchronously by exhibition-gallery.js. Never
  // append content directly to an unfinished anchor: doing so made transient
  // empty/half-rendered cards visible in large datasets such as Gijón.
  const node = card.querySelector("[data-exhibition-opening-hours]");
  if (!node) return;
  if (!hours) {
    node.hidden = true;
    node.replaceChildren();
    return;
  }

  node.hidden = false;
  const icon = document.createElement("span");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "◷";
  const copy = document.createElement("span");
  copy.textContent = `Horario del recinto: ${hours}`;
  node.replaceChildren(icon, copy);
}

function patchGroupCard(card) {
  if (!card.classList.contains("exhibition-venue-card")) return;
  const ids = String(card.dataset.eventGroup || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (!ids.length) return;

  const ranges = ids
    .map((id) => eventsById.get(id))
    .filter(Boolean)
    .map(explicitVenueHours)
    .filter(Boolean);
  const counts = new Map();
  for (const range of ranges) counts.set(range, (counts.get(range) || 0) + 1);
  const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));

  // A group-level venue schedule is shown only when the evidence is unambiguous:
  // one explicit range, or the same range repeated by at least two records. If
  // sources conflict, keep the header silent and leave each exhibition's own
  // schedule visible inside the group instead of publishing a guessed opening time.
  const hours = ranked.length === 1
    ? ranked[0][0]
    : ranked.length > 1 && ranked[0][1] >= 2 && ranked[0][1] > ranked[1][1]
      ? ranked[0][0]
      : null;

  setGroupedOpeningHours(card, hours);
}

function patchCards() {
  if (!datedGrid || !eventsById.size) return;
  for (const card of datedGrid.querySelectorAll(".event-card")) {
    if (card.dataset.eventGroup) patchGroupCard(card);
    else patchStandaloneCard(card);
  }
}

async function loadEventsForCurrentCity() {
  const cityId = currentCityId();
  if (!cityId) return;
  if (loadedCity === cityId && eventsById.size) {
    patchCards();
    return;
  }

  const token = ++loadingToken;
  loadedCity = cityId;
  eventsById = new Map();
  try {
    const response = await fetch(CITY_CONFIG[cityId].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    if (token !== loadingToken || !Array.isArray(dataset.events)) return;
    eventsById = new Map(dataset.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
    patchCards();
  } catch {
    eventsById = new Map();
  }
}

if (datedGrid) {
  new MutationObserver(() => patchCards()).observe(datedGrid, { childList: true, subtree: true });
}

new MutationObserver(() => {
  loadedCity = null;
  eventsById = new Map();
  loadEventsForCurrentCity();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

loadEventsForCurrentCity();