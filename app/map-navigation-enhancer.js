import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";
import { googleMapsDirectionsUrl } from "./public-presentation-rules.mjs?v=20260822-mapnav1";

let eventIndex = new Map();
let activeCityId = "";
let indexedRevision = 0;
let applyQueued = false;

function syncRuntimeIndex() {
  const requestedCity = String(document.documentElement.dataset.city || "").trim();
  const snapshot = getAgendaRuntimeSnapshot(requestedCity || null);
  if (!snapshot) return false;
  if (activeCityId === snapshot.cityId && indexedRevision === snapshot.revision && eventIndex.size) return true;
  activeCityId = snapshot.cityId;
  indexedRevision = snapshot.revision;
  const items = [...(snapshot.events || []), ...(snapshot.secondaryPrograms || [])];
  eventIndex = new Map(items
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));
  return eventIndex.size > 0;
}

function sameVenue(a, b) {
  const key = (event) => [event?.location?.venue, event?.location?.city]
    .map((value) => String(value || "").replace(/\s+/g, " ").trim().toLocaleLowerCase("es"))
    .join("|");
  const first = key(a);
  return Boolean(first && first === key(b));
}

function styleMapLink(link) {
  if (!(link instanceof HTMLAnchorElement)) return;
  link.classList.add("map-location-link");
  link.style.cssText = [
    "display:inline-flex",
    "align-items:center",
    "justify-content:center",
    "margin-left:.2em",
    "font-size:1.04em",
    "font-weight:800",
    "line-height:1",
    "opacity:.9",
    "text-decoration:none",
    "vertical-align:.02em",
  ].join(";");
}

function makeMapLink(event, { grouped = false } = {}) {
  const href = googleMapsDirectionsUrl(event);
  if (!href) return null;
  const venue = String(event?.location?.venue || "").trim();
  const link = document.createElement("a");
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.title = "Abrir ubicación en Google Maps";
  link.setAttribute("aria-label", venue ? `Abrir ${venue} en Google Maps` : "Abrir ubicación en Google Maps");
  link.textContent = "↗";
  if (grouped) link.dataset.groupedVenueMap = "";
  styleMapLink(link);
  link.addEventListener("click", (click) => click.stopPropagation());
  return link;
}

function ensureMapLink(container, event, options = {}) {
  if (!(container instanceof Element)) return false;
  const href = googleMapsDirectionsUrl(event) || "";
  const existing = container.querySelector(":scope > .map-location-link");
  if (!href) {
    if (existing?.hasAttribute("data-grouped-venue-map")) existing.remove();
    return false;
  }
  if (existing) {
    existing.href = href;
    styleMapLink(existing);
    return true;
  }
  const link = makeMapLink(event, options);
  if (!link) return false;
  container.append(document.createTextNode(" "), link);
  return true;
}

function cardLocationNode(card) {
  const facts = [...card.querySelectorAll(".card-fact")];
  const locationFact = facts.find((row) => row.querySelector(".sr-only")?.textContent.trim().startsWith("Lugar:"));
  if (locationFact) return locationFact.querySelector(":scope > span:last-child");

  const schedule = card.querySelector(":scope > h4 + p");
  return card.querySelector(":scope > p[data-location-display]")
    || [...card.querySelectorAll(":scope > p")].find((node) => (
      node !== schedule
      && !node.classList.contains("venue-opening-hours")
      && !node.hasAttribute("data-exhibition-opening-hours")
    ))
    || null;
}

function enhanceCard(card) {
  const event = eventIndex.get(String(card.dataset.eventId || "").trim());
  if (!event) return;
  ensureMapLink(cardLocationNode(card), event);
}

function groupEvents(card) {
  return String(card.dataset.eventGroup || "")
    .split(",")
    .map((id) => eventIndex.get(id.trim()))
    .filter(Boolean);
}

function verifiedGroupNavigationEvent(events) {
  if (!events.length) return null;
  const eligible = events
    .map((event) => ({ event, href: googleMapsDirectionsUrl(event) }))
    .filter((entry) => entry.href);
  if (!eligible.length) return null;
  if (!events.every((event) => sameVenue(event, eligible[0].event))) return null;
  const destinations = new Set(eligible.map((entry) => entry.href));
  if (destinations.size !== 1) return null;
  return eligible[0].event;
}

function enhanceGroupedCard(card) {
  if (!card.classList.contains("exhibition-venue-card")) return;
  const events = groupEvents(card);
  const fallback = verifiedGroupNavigationEvent(events);
  const heading = card.querySelector(".exhibition-venue-heading h4");
  if (heading && fallback) ensureMapLink(heading, fallback, { grouped: true });

  for (const row of card.querySelectorAll("[data-grouped-event-id]")) {
    const event = eventIndex.get(String(row.dataset.groupedEventId || "").trim());
    const location = row.querySelector(".grouped-exhibition-location");
    if (!event || !location) continue;
    const ownHref = googleMapsDirectionsUrl(event);
    const navigationEvent = ownHref ? event : (fallback && sameVenue(event, fallback) ? fallback : null);
    if (navigationEvent) ensureMapLink(location, navigationEvent);
  }
}

function enhanceDetail(dialog) {
  const event = eventIndex.get(String(dialog.dataset.eventDetail || "").trim());
  if (!event) return;
  const fact = [...dialog.querySelectorAll(".event-detail-fact")]
    .find((row) => row.querySelector("strong")?.textContent.trim() === "Lugar");
  const copy = fact?.querySelector("span:last-child");
  ensureMapLink(copy, event);
}

function apply() {
  applyQueued = false;
  if (!syncRuntimeIndex()) return;
  document.querySelectorAll(".map-location-link").forEach(styleMapLink);
  document.querySelectorAll(".event-card[data-event-id]").forEach(enhanceCard);
  document.querySelectorAll(".event-card[data-event-group]").forEach(enhanceGroupedCard);
  document.querySelectorAll("dialog[data-event-detail]").forEach(enhanceDetail);
}

function queueApply() {
  if (applyQueued) return;
  applyQueued = true;
  queueMicrotask(apply);
}

for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:cards-enriched",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, queueApply);
}
window.addEventListener("pageshow", queueApply, { passive: true });
document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("[data-open-event]")) setTimeout(queueApply, 0);
});
queueApply();
