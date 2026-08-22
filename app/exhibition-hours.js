import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";
import { dailyExhibitionHours, nextDailyExhibitionOpening } from "./date-aware-exhibition-hours.mjs?v=20260821-next-hours1";
import { visibleReferenceDateKey } from "./filter-reference-date.mjs?v=20260821-visible-date1";
import { nextVenueOpeningForDate, venueHoursForDate } from "./venue-hours.mjs?v=20260821-next-hours1";

const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);
const DEFAULT_TIMEZONE = "UTC";
const datedGrid = document.querySelector("[data-dated-grid]");
let indexedCity = null;
let indexedRevision = 0;
let indexedTimezone = DEFAULT_TIMEZONE;
let indexedLocale = "es";
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
  indexedTimezone = snapshot.city?.timezone || DEFAULT_TIMEZONE;
  indexedLocale = snapshot.city?.locale || "es";
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

function formatOpeningDate(dateKey) {
  const match = String(dateKey || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return dateKey || "";
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12));
  return new Intl.DateTimeFormat(indexedLocale, {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(date).replace(/\.$/, "");
}

function closedWithNextOpening(nextOpening, dateField, hoursField) {
  if (!nextOpening) return "Cerrado";
  const date = formatOpeningDate(nextOpening[dateField]);
  const hours = String(nextOpening[hoursField] || "").trim();
  if (!(date && hours)) return "Cerrado";
  return `Cerrado · Próxima apertura: ${date} · ${hours}`;
}

function explicitVenueHours(event) {
  if (!isExhibition(event)) return null;
  const referenceDate = referenceDateKey();

  // Event-specific weekly hours are authoritative. If they say the exhibition
  // is closed on the selected date, find the next opening from that same
  // schedule before consulting any generic venue registry.
  const scheduleHours = dailyExhibitionHours(event?.schedule, {
    timezone: indexedTimezone,
    referenceDate,
  });
  if (scheduleHours?.label) {
    if (!scheduleHours.closed && !/^cerrado\b/i.test(scheduleHours.label)) return scheduleHours.label;
    const next = nextDailyExhibitionOpening(event?.schedule, {
      timezone: indexedTimezone,
      referenceDate,
      maxDays: 7,
    });
    return closedWithNextOpening(next, "referenceDateKey", "label");
  }

  const venueHours = venueHoursForDate(event, indexedCity, referenceDate);
  if (!venueHours?.display) return null;
  if (!/^cerrado\b/i.test(venueHours.display)) return venueHours.display;
  const next = nextVenueOpeningForDate(event, indexedCity, referenceDate, { max_days: 7 });
  return closedWithNextOpening(next, "reference_date", "display");
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
  let hours = commonExplicitHours(events);
  if (!hours) {
    for (const event of events) {
      hours = explicitVenueHours(event);
      if (hours) break;
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