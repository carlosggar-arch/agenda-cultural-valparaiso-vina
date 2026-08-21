import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { dailyExhibitionHours } from "./date-aware-exhibition-hours.mjs?v=20260821-date-hours1";

const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);
const datedGrid = document.querySelector("[data-dated-grid]");
let indexedCity = null;
let indexedRevision = 0;
let indexedTimezone = "America/Santiago";
let eventsById = new Map();
let patchQueued = false;

function currentCityId() {
  return String(document.documentElement.dataset.city || "").trim();
}

function syncRuntimeIndex() {
  const cityId = currentCityId();
  const snapshot = getAgendaRuntimeSnapshot(cityId);
  if (!snapshot) return false;
  if (indexedCity === cityId && indexedRevision === snapshot.revision && eventsById.size) return true;
  indexedCity = cityId;
  indexedRevision = snapshot.revision;
  indexedTimezone = snapshot.city?.timezone || "America/Santiago";
  eventsById = new Map(snapshot.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  return true;
}

function isExhibition(event) {
  const primaryId = String(event?.primary_category?.id || "").trim();
  if (EXHIBITION_IDS.has(primaryId)) return true;
  return (event?.categories || []).some((category) => EXHIBITION_IDS.has(String(category?.id || "").trim()));
}

function explicitVenueHours(event) {
  if (!isExhibition(event)) return null;
  return dailyExhibitionHours(event?.schedule, {
    timezone: indexedTimezone,
    now: new Date(),
  })?.label || null;
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

function groupedOpeningHoursNode(card, create = false) {
  const candidates = [...card.querySelectorAll("[data-exhibition-opening-hours], .exhibition-venue-hours")];
  let node = candidates[0] || null;
  if (node) {
    node.dataset.exhibitionOpeningHours = "";
    for (const duplicate of candidates.slice(1)) duplicate.remove();
    return node;
  }
  if (!create) return null;
  const facts = card.querySelector(".exhibition-venue-facts");
  if (!facts) return null;
  node = document.createElement("p");
  node.className = "venue-opening-hours exhibition-venue-hours";
  node.dataset.exhibitionOpeningHours = "";
  facts.append(node);
  return node;
}

function setGroupedOpeningHours(card, hours) {
  const node = groupedOpeningHoursNode(card, Boolean(hours));
  if (!node) return;
  if (!hours) {
    node.remove();
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
  const ids = String(card.dataset.eventGroup || "").split(",").map((value) => value.trim()).filter(Boolean);
  if (!ids.length) return;
  const events = ids.map((id) => eventsById.get(id)).filter(Boolean);
  const labels = events.map(explicitVenueHours);
  const safeCommonHours = events.length > 0
    && labels.length === events.length
    && labels.every(Boolean)
    && new Set(labels).size === 1
    ? labels[0]
    : null;
  setGroupedOpeningHours(card, safeCommonHours);
}

function patchCards() {
  patchQueued = false;
  if (!datedGrid) return;
  const runtimeReady = syncRuntimeIndex();
  if (!runtimeReady) return;
  for (const card of datedGrid.querySelectorAll(".event-card")) {
    if (card.dataset.eventGroup) patchGroupCard(card);
    else patchStandaloneCard(card);
  }
}

function queuePatch() {
  if (patchQueued) return;
  patchQueued = true;
  queueMicrotask(patchCards);
}

for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:cards-enriched",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, queuePatch);
}
window.addEventListener("pageshow", queuePatch, { passive: true });
queuePatch();
