import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { scheduleForGijonEvent } from "./gijon-venue-hours.js?v=20260820-hours1";

const STYLE_ID = "gijon-core-card-images";
const CITY_ID = "gijon";
const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);
let queued = false;
let indexedRevision = 0;
let byId = new Map();

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    html[data-city="gijon"] .event-card > .gijon-card-media {
      position: relative;
      height: clamp(118px, 15vw, 175px);
      margin: -1.2rem -1.2rem .25rem;
      overflow: hidden;
      border-radius: 1.15rem 1.15rem .65rem .65rem;
      background: color-mix(in srgb, var(--surface-tint) 78%, #fff);
    }
    html[data-city="gijon"] .event-card > .gijon-card-media img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    html[data-city="gijon"] .event-card > .gijon-venue-hours {
      margin-top: -.15rem;
      font-weight: 700;
    }
    @media (max-width: 560px) {
      html[data-city="gijon"] .event-card > .gijon-card-media { height: 170px; }
    }
  `;
  document.head.append(style);
}

function safeImage(event) {
  const candidate = event?.image?.url || event?.image_url || event?.media?.image || "";
  if (!candidate) return null;
  try {
    const url = new URL(String(candidate), window.location.href);
    if (!["http:", "https:"].includes(url.protocol)) return null;
    return {
      url: url.href,
      alt: String(event?.image?.alt || event?.title || "Imagen de la actividad").trim(),
    };
  } catch {
    return null;
  }
}

function addImage(card, event) {
  if (!card || card.querySelector(":scope > .gijon-card-media")) return;
  const image = safeImage(event);
  if (!image) return;
  const media = document.createElement("div");
  media.className = "gijon-card-media";
  const img = document.createElement("img");
  img.src = image.url;
  img.alt = image.alt;
  img.loading = "lazy";
  img.decoding = "async";
  img.addEventListener("error", () => media.remove(), { once: true });
  media.append(img);
  card.prepend(media);
}

function isExhibition(event) {
  const primaryId = String(event?.primary_category?.id || "").trim();
  if (EXHIBITION_IDS.has(primaryId)) return true;
  return (event?.categories || []).some((category) => EXHIBITION_IDS.has(String(category?.id || "").trim()));
}

function verifiedVenueHours(event) {
  if (!event) return null;
  const schedule = scheduleForGijonEvent(event) || event.schedule || {};
  const display = String(schedule?.opening_hours?.display_text || "").replace(/\s+/g, " ").trim();
  return display || null;
}

function setVenueHours(card, hours) {
  if (!card) return;
  let node = card.querySelector(":scope > .gijon-venue-hours");
  if (!hours) {
    node?.remove();
    return;
  }
  if (!node) {
    node = document.createElement("p");
    node.className = "venue-opening-hours gijon-venue-hours";
    const schedule = card.querySelector(":scope > h4 + p");
    if (schedule) schedule.insertAdjacentElement("afterend", node);
    else card.querySelector(":scope > h4")?.insertAdjacentElement("afterend", node);
  }
  node.textContent = `Horario del recinto: ${hours}`;
}

function syncIndex() {
  if (String(document.documentElement.dataset.city || "") !== CITY_ID) return false;
  const snapshot = getAgendaRuntimeSnapshot(CITY_ID);
  if (!snapshot) return false;
  if (indexedRevision === snapshot.revision && byId.size) return true;
  indexedRevision = snapshot.revision;
  byId = new Map(snapshot.events
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));
  return true;
}

function enhanceCards() {
  queued = false;
  if (!syncIndex()) return;
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    const event = byId.get(String(card.dataset.eventId || ""));
    addImage(card, event);

    // Exhibition visit hours are date-sensitive and are owned by the shared
    // exhibition-hours.js layer. Keeping this Gijón media enricher out of that
    // path prevents a second writer from restoring the full weekly schedule or
    // racing with the selected-date presentation.
    if (!isExhibition(event)) setVenueHours(card, verifiedVenueHours(event));
  }

  // Shared exhibition groups are owned entirely by exhibition-groups.js.
  // Gijón-specific enrichment must never prepend a second hero image or venue
  // hours to that common component.
  for (const card of document.querySelectorAll(".event-card[data-event-group]")) {
    if (card.dataset.category === "exposiciones" || card.classList.contains("exhibition-venue-card")) continue;
    const ids = String(card.dataset.eventGroup || "").split(",").map((id) => id.trim()).filter(Boolean);
    const events = ids.map((id) => byId.get(id)).filter(Boolean);
    const imageEvent = events.find((candidate) => safeImage(candidate));
    addImage(card, imageEvent);
    const hours = events.map(verifiedVenueHours).find(Boolean) || null;
    setVenueHours(card, hours);
  }
}

function queueEnhancement() {
  if (queued) return;
  queued = true;
  queueMicrotask(enhanceCards);
}

installStyles();
window.addEventListener("vivamos:agenda-data-ready", queueEnhancement);
window.addEventListener("vivamos:agenda-rendered", queueEnhancement);
window.addEventListener("vivamos:exhibition-groups-rendered", queueEnhancement);
window.addEventListener("pageshow", queueEnhancement, { passive: true });
queueEnhancement();