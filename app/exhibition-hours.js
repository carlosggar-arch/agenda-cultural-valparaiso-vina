import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { venueRecordForEvent, venueRecordForName } from "./venue-identity.mjs?v=20260820-venues1";

const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);
const EXHIBITION_CARD_POLISH_STYLE_ID = "exhibition-card-polish-20260820";
const datedGrid = document.querySelector("[data-dated-grid]");
let indexedCity = null;
let indexedRevision = 0;
let eventsById = new Map();
let patchQueued = false;

function ensureExhibitionCardPolishStyles() {
  if (document.getElementById(EXHIBITION_CARD_POLISH_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = EXHIBITION_CARD_POLISH_STYLE_ID;
  style.textContent = `
    .grouped-exhibition-item {
      height: auto !important;
      min-height: 96px !important;
      max-height: none !important;
      align-items: start !important;
      overflow: visible !important;
    }

    .grouped-exhibition-media,
    .grouped-exhibition-copy,
    .grouped-exhibition-actions {
      align-self: start !important;
    }

    .grouped-exhibition-copy {
      padding-top: 1px !important;
      overflow: visible !important;
    }

    .grouped-exhibition-copy strong {
      margin-bottom: 3px !important;
    }

    .exhibition-group-list {
      max-height: 306px !important;
    }

    .exhibition-group-list:not(:has(> .grouped-exhibition-item:nth-child(4))) {
      max-height: none !important;
      overflow-y: visible !important;
    }

    @media (max-width: 900px) {
      .grouped-exhibition-item { min-height: 94px !important; }
      .exhibition-group-list { max-height: 300px !important; }
    }

    @media (max-width: 560px) {
      .grouped-exhibition-item { min-height: 92px !important; }
      .exhibition-group-list { max-height: 294px !important; }
    }
  `;
  document.head.append(style);
}

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
  eventsById = new Map(snapshot.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  return true;
}

function isExhibition(event) {
  const primaryId = String(event?.primary_category?.id || "").trim();
  if (EXHIBITION_IDS.has(primaryId)) return true;
  return (event?.categories || []).some((category) => EXHIBITION_IDS.has(String(category?.id || "").trim()));
}

function validTime(value) {
  return /^\d{2}:\d{2}$/.test(String(value || "").trim());
}

function isMultiDayVisit(event) {
  const schedule = event?.schedule || {};
  if (schedule.mode === "multi_day") return true;
  const start = String(schedule.start || "").slice(0, 10);
  const end = String(schedule.end || "").slice(0, 10);
  return Boolean(start && end && start !== end);
}

function knownVenueHours(event) {
  if (!isExhibition(event) || !isMultiDayVisit(event)) return null;
  return venueRecordForEvent(event)?.opening_hours?.display || null;
}

function explicitVenueHours(event) {
  if (!isExhibition(event)) return null;
  const schedule = event?.schedule || {};
  const openingHours = schedule.opening_hours || {};
  const opening = String(schedule.opening_time || openingHours.opening_time || "").trim();
  const closing = String(schedule.closing_time || openingHours.closing_time || "").trim();
  if (validTime(opening) && validTime(closing)) return `${opening}–${closing}`;
  const display = String(openingHours.display_text || "").replace(/\s+/g, " ").trim();
  if (display && /\b(?:[01]?\d|2[0-3]):[0-5]\d\b/.test(display)) return display;
  return knownVenueHours(event);
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

function knownGroupedVenueHours(card) {
  const name = card.querySelector(".exhibition-venue-heading h4")?.textContent || "";
  return venueRecordForName(name)?.opening_hours?.display || null;
}

function patchGroupCard(card) {
  if (!card.classList.contains("exhibition-venue-card")) return;
  const ids = String(card.dataset.eventGroup || "").split(",").map((value) => value.trim()).filter(Boolean);
  if (!ids.length) return;
  const ranges = ids.map((id) => eventsById.get(id)).filter(Boolean).map(explicitVenueHours).filter(Boolean);
  const counts = new Map();
  for (const range of ranges) counts.set(range, (counts.get(range) || 0) + 1);
  const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  let hours = ranked.length === 1
    ? ranked[0][0]
    : ranked.length > 1 && ranked[0][1] >= 2 && ranked[0][1] > ranked[1][1]
      ? ranked[0][0]
      : null;
  if (!hours) hours = knownGroupedVenueHours(card);
  setGroupedOpeningHours(card, hours);
}

function patchCards() {
  patchQueued = false;
  if (!datedGrid) return;
  const runtimeReady = syncRuntimeIndex();
  for (const card of datedGrid.querySelectorAll(".event-card")) {
    if (card.dataset.eventGroup) patchGroupCard(card);
    else if (runtimeReady) patchStandaloneCard(card);
  }
}

function queuePatch() {
  if (patchQueued) return;
  patchQueued = true;
  queueMicrotask(patchCards);
}

ensureExhibitionCardPolishStyles();
for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:cards-enriched",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, queuePatch);
}
queuePatch();
