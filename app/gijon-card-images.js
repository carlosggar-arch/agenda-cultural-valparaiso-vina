import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";

const STYLE_ID = "gijon-core-card-images";
const CITY_ID = "gijon";
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

function enhanceImages() {
  queued = false;
  if (!syncIndex()) return;
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    addImage(card, byId.get(String(card.dataset.eventId || "")));
  }
  for (const card of document.querySelectorAll(".event-card[data-event-group]")) {
    const ids = String(card.dataset.eventGroup || "").split(",").map((id) => id.trim()).filter(Boolean);
    const event = ids.map((id) => byId.get(id)).find((candidate) => safeImage(candidate));
    addImage(card, event);
  }
}

function queueEnhancement() {
  if (queued) return;
  queued = true;
  queueMicrotask(enhanceImages);
}

installStyles();
window.addEventListener("vivamos:agenda-data-ready", queueEnhancement);
window.addEventListener("vivamos:agenda-rendered", queueEnhancement);
window.addEventListener("pageshow", queueEnhancement, { passive: true });
queueEnhancement();
