import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { venueHoursForEvents } from "./venue-hours.mjs?v=20260820-hours-contract1";

const datedGrid = document.querySelector("[data-dated-grid]");
let indexedCity = null;
let indexedRevision = 0;
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
  eventsById = new Map(snapshot.events
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));
  return true;
}

function hoursFor(events) {
  return venueHoursForEvents(events, currentCityId())?.display || null;
}

function standaloneHoursNode(card, create = false) {
  let node = card.querySelector(":scope > .venue-opening-hours");
  if (node || !create) return node;
  node = document.createElement("p");
  node.className = "venue-opening-hours";
  const schedule = card.querySelector(":scope > h4 + p");
  if (schedule) schedule.insertAdjacentElement("afterend", node);
  else card.querySelector(":scope > h4")?.insertAdjacentElement("afterend", node);
  return node;
}

function patchStandaloneCard(card) {
  const id = String(card.dataset.eventId || "").trim();
  if (!id) return;
  const event = eventsById.get(id);
  const hours = event ? hoursFor([event]) : null;
  const node = standaloneHoursNode(card, Boolean(hours));
  if (!node) return;
  if (!hours) {
    node.remove();
    return;
  }
  node.hidden = false;
  node.textContent = `Horario del recinto: ${hours}`;
}

function groupedHoursNode(card, create = false) {
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

function patchGroupCard(card) {
  if (!card.classList.contains("exhibition-venue-card")) return;
  const ids = String(card.dataset.eventGroup || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (!ids.length) return;
  const events = ids.map((id) => eventsById.get(id)).filter(Boolean);
  const hours = hoursFor(events);
  const node = groupedHoursNode(card, Boolean(hours));
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

function patchCards() {
  patchQueued = false;
  if (!datedGrid || !syncRuntimeIndex()) return;
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
