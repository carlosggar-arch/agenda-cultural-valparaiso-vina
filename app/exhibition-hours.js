import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { venueRecordForEvent, venueRecordForName } from "./venue-identity.mjs?v=20260820-venues1";
import { dailyExhibitionHours } from "./date-aware-exhibition-hours.mjs?v=20260821-date-hours1";
import { visibleReferenceDateKey } from "./filter-reference-date.mjs?v=20260821-visible-date1";
import { gijonVenueHoursForDate } from "./gijon-venue-hours.js?v=20260821-visible-date1";

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

function referenceDateKey() {
  return visibleReferenceDateKey({ timezone: indexedTimezone });
}

function structuredRegistryHours(record, referenceDate) {
  const hours = record?.opening_hours;
  if (!hours || typeof hours !== "object") return null;
  const hasStructuredWeekdays = Array.isArray(hours.open_weekdays) && hours.open_weekdays.length > 0;
  const hasStructuredRange = /^\d{2}:\d{2}$/.test(String(hours.opening_time || ""))
    && /^\d{2}:\d{2}$/.test(String(hours.closing_time || ""));
  if (!(hasStructuredWeekdays || hasStructuredRange)) return null;
  return dailyExhibitionHours({ opening_hours: hours }, {
    timezone: indexedTimezone,
    referenceDate,
  })?.label || null;
}

function explicitVenueHours(event) {
  if (!isExhibition(event)) return null;
  const referenceDate = referenceDateKey();
  const scheduleHours = dailyExhibitionHours(event?.schedule, {
    timezone: indexedTimezone,
    referenceDate,
  })?.label || null;
  if (scheduleHours) return scheduleHours;

  if (indexedCity === "gijon") {
    return gijonVenueHoursForDate(event, referenceDate)?.display || null;
  }

  return structuredRegistryHours(venueRecordForEvent(event), referenceDate);
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

function commonExplicitHours(events) {
  const labels = events.map(explicitVenueHours);
  return events.length > 0
    && labels.length === events.length
    && labels.every(Boolean)
    && new Set(labels).size === 1
    ? labels[0]
    : null;
}

function patchGroupCard(card) {
  if (!card.classList.contains("exhibition-venue-card")) return;
  const ids = String(card.dataset.eventGroup || "").split(",").map((value) => value.trim()).filter(Boolean);
  if (!ids.length) return;
  const events = ids.map((id) => eventsById.get(id)).filter(Boolean);
  let hours = null;

  if (indexedCity === "gijon") {
    // A grouped card represents one venue. Its header must therefore use the
    // venue's date-specific opening hours, not compare event-level schedules
    // across all exhibitions in the group. Those schedules can legitimately
    // differ even though the museum opening hours are identical.
    const referenceDate = referenceDateKey();
    for (const event of events) {
      const venueHours = gijonVenueHoursForDate(event, referenceDate)?.display || null;
      if (venueHours) {
        hours = venueHours;
        break;
      }
    }
    if (!hours) hours = commonExplicitHours(events);
  } else {
    hours = commonExplicitHours(events);
    if (!hours) {
      const labels = events.map(explicitVenueHours);
      if (labels.every((label) => !label)) {
        const venueName = card.querySelector(".exhibition-venue-heading h4")?.textContent || "";
        hours = structuredRegistryHours(venueRecordForName(venueName), referenceDateKey());
      }
    }
  }

  setGroupedOpeningHours(card, hours);
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
document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("[data-combined-when] [data-filter-value]")) setTimeout(queuePatch, 0);
});
document.addEventListener("change", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.matches("[data-date-from], [data-date-to]")) setTimeout(queuePatch, 0);
});
queuePatch();