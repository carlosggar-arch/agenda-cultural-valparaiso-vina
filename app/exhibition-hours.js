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

function openingTime(event) {
  const enriched = event?.editorial?.venue_hours_enriched === true
    || event?.editorial?.visit_hours_enriched === true;
  if (!enriched || !isExhibition(event)) return null;

  const value = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  if (!value || /^\d{4}-\d{2}-\d{2}$/.test(String(value))) return null;

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const city = CITY_CONFIG[currentCityId()];
  if (!city) return null;

  return new Intl.DateTimeFormat(city.locale || "es", {
    timeZone: city.timezone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
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
  const time = event ? openingTime(event) : null;
  const schedule = card.querySelector(":scope > h4 + p");
  const existing = card.querySelector(":scope > .venue-opening-hours");

  if (!time) {
    existing?.remove();
    return;
  }

  if (!existing) {
    const node = document.createElement("p");
    node.className = "venue-opening-hours";
    node.textContent = `Horario de apertura: ${time}`;
    schedule?.insertAdjacentElement("afterend", node);
  } else if (existing.textContent !== `Horario de apertura: ${time}`) {
    existing.textContent = `Horario de apertura: ${time}`;
  }
}

function patchGroupCard(card) {
  const ids = String(card.dataset.eventGroup || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (!ids.length) return;

  const times = [...new Set(ids.map((id) => eventsById.get(id)).filter(Boolean).map(openingTime).filter(Boolean))];
  const details = card.querySelector(":scope > .exhibition-group-details");
  const text = times.length === 1
    ? `Horario de apertura del recinto: ${times[0]}`
    : times.length > 1
      ? `Horarios de apertura: ${times.join(" · ")}`
      : "";
  upsertOpeningParagraph(card, text, details);
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
