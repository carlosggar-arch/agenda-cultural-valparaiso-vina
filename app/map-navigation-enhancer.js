import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";
import { googleMapsDirectionsUrl } from "./public-presentation-rules.mjs?v=20260822-mapnav1";

const STYLE_ID = "vivamos-map-navigation-styles";
const SVG_NS = "http://www.w3.org/2000/svg";
let eventIndex = new Map();
let activeCityId = "";
let indexedRevision = 0;
let applyQueued = false;

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .map-location-link {
      display:inline-flex !important;
      align-items:center !important;
      justify-content:center !important;
      position:relative;
      flex:0 0 25px !important;
      box-sizing:border-box;
      width:25px !important;
      height:25px !important;
      min-width:25px !important;
      min-height:25px !important;
      max-width:25px !important;
      max-height:25px !important;
      margin-left:.24rem !important;
      padding:0;
      border:1px solid color-mix(in srgb,var(--brand,#174f46) 22%,transparent);
      border-radius:4px;
      background:color-mix(in srgb,var(--brand,#174f46) 8%,#fff);
      color:var(--brand,#174f46) !important;
      line-height:1 !important;
      opacity:.92 !important;
      text-decoration:none !important;
      vertical-align:middle !important;
      transform:none !important;
      transition:background .14s ease,border-color .14s ease,opacity .14s ease;
    }
    .map-location-link::before {
      content:"";
      position:absolute;
      width:44px;
      height:44px;
      left:50%;
      top:50%;
      transform:translate(-50%,-50%);
    }
    .map-location-link-icon {
      display:block;
      width:18px;
      height:18px;
      flex:0 0 18px;
      pointer-events:none;
    }
    .map-location-link:hover,
    .map-location-link:focus-visible {
      background:color-mix(in srgb,var(--brand,#174f46) 14%,#fff);
      border-color:color-mix(in srgb,var(--brand,#174f46) 38%,transparent);
      opacity:1 !important;
      text-decoration:none !important;
    }
    .map-location-link:focus-visible {
      outline:2px solid color-mix(in srgb,var(--brand,#174f46) 32%,transparent);
      outline-offset:2px;
    }
    .card-fact--map-location {
      align-items:center !important;
    }
    .card-fact--map-location > .card-fact-icon {
      margin-top:0 !important;
      align-self:center;
    }
    .card-fact--map-location > span:last-child,
    .grouped-exhibition-location,
    .event-detail-fact--map-location > span:last-child {
      line-height:1.35;
    }
  `;
  document.head.append(style);
}

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

function markLocationContainer(container) {
  if (!(container instanceof Element)) return;
  const fact = container.closest(".card-fact");
  if (fact) fact.classList.add("card-fact--map-location");
  const detailFact = container.closest(".event-detail-fact");
  if (detailFact) detailFact.classList.add("event-detail-fact--map-location");
}

function makeMapIcon() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("map-location-link-icon");
  svg.setAttribute("viewBox", "0 0 18 18");
  svg.setAttribute("width", "18");
  svg.setAttribute("height", "18");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");

  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", "M4 14L14 4M7 4h7v7");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2.2");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.append(path);
  return svg;
}

function styleMapLink(link) {
  if (!(link instanceof HTMLAnchorElement)) return;
  link.classList.add("map-location-link");
  link.removeAttribute("style");
  const icon = link.querySelector(":scope > .map-location-link-icon");
  if (!icon) link.replaceChildren(makeMapIcon());
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
  link.append(makeMapIcon());
  if (grouped) link.dataset.groupedVenueMap = "";
  styleMapLink(link);
  link.addEventListener("click", (click) => click.stopPropagation());
  return link;
}

function ensureMapLink(container, event, options = {}) {
  if (!(container instanceof Element)) return false;
  markLocationContainer(container);
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
  installStyles();
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

installStyles();
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
