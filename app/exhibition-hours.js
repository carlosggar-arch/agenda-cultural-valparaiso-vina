import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";

const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);
const MHNV_HOURS = "Mar–vie 10:00–18:00 · sáb 11:00–16:00 · dom/lun/festivos cerrado";
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
    /* Keep three compact exhibition rows fully visible before internal scrolling. */
    .exhibition-group-list {
      max-height: 228px !important;
    }
    @media (max-width: 900px) {
      .exhibition-group-list {
        max-height: 222px !important;
      }
    }
    @media (max-width: 560px) {
      .exhibition-group-list {
        max-height: 216px !important;
      }
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

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
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
  const identity = fold([
    event?.location?.venue,
    event?.organizer,
    event?.source_name,
  ].filter(Boolean).join(" "));
  if (identity.includes("museo de historia natural de valparaiso")) return MHNV_HOURS;
  return null;
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

  // Older/static group renderers can provide the same venue-hours row without
  // the data hook. Reuse that row and remove any duplicate instead of adding a
  // second identical opening-hours line (seen, for example, at Palacio Rioja).
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
  const ranges = ids.map((id) => eventsById.get(id)).filter(Boolean).map(explicitVenueHours).filter(Boolean);
  const counts = new Map();
  for (const range of ranges) counts.set(range, (counts.get(range) || 0) + 1);
  const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const hours = ranked.length === 1
    ? ranked[0][0]
    : ranked.length > 1 && ranked[0][1] >= 2 && ranked[0][1] > ranked[1][1]
      ? ranked[0][0]
      : null;
  setGroupedOpeningHours(card, hours);
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
