import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";

const CATEGORY_IMAGES = Object.freeze({
  musica: "../assets/categoria-musica.jpg",
  cine: "../assets/categoria-cine.jpg",
  teatro: "../assets/categoria-teatro.jpg",
  exposiciones: "../assets/categoria-exposiciones.jpg",
  museos: "../assets/categoria-exposiciones.jpg",
  "cursos-talleres": "../assets/categoria-talleres.jpg",
  "cursos-talleres-campus": "../assets/categoria-talleres.jpg",
  deportes: "../assets/categoria-deportes.jpg",
  gastronomia: "../assets/categoria-gastronomia.jpg",
  ferias: "../assets/categoria-gastronomia.jpg",
  "naturaleza-montana": "../assets/categoria-naturaleza.jpg",
  cultura: "../assets/categoria-cultura.jpg",
});

const GENERIC_PROVIDER_HOSTS = /(^|\.)(passline\.com|eventrid\.cl|ticketplus\.(cl|com)|ticketmaster\.cl|puntoticket\.com|ticketpro\.(cl|com|net)|tickets\.cl|ticketera\.cl|ticketfacil\.cl|portaltickets\.cl|goignis\.cl)$/i;
const GENERIC_PROVIDER_PATH = /(?:^|\/)(?:assets?\/(?:img|images?)\/)?(?:icon|logo|favicon|placeholder|default|no[-_]?image|sin[-_]?imagen)(?:[-_.\/]|$)/i;
const GENERIC_AVATAR_HOSTS = /(^|\.)gravatar\.com$/i;

let scanQueued = false;
let indexedRevision = 0;
let eventIndex = new Map();

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function syncRuntimeIndex() {
  const snapshot = getAgendaRuntimeSnapshot();
  if (!snapshot) return;
  if (snapshot.revision === indexedRevision && eventIndex.size) return;
  indexedRevision = snapshot.revision;
  eventIndex = new Map(snapshot.events
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));
}

function categoryIdForCard(card) {
  const event = eventIndex.get(String(card?.dataset?.eventId || "").trim());
  const runtimeCategory = event?.primary_category?.id || event?.categories?.[0]?.id;
  const explicit = fold(runtimeCategory || card?.dataset?.category);
  if (explicit && CATEGORY_IMAGES[explicit]) return explicit;
  const runtimeLabel = event?.primary_category?.label || event?.categories?.[0]?.label;
  const label = fold(runtimeLabel || card?.querySelector(".meta")?.textContent || card?.querySelector(".event-card-placeholder-label")?.textContent);
  if (/musica/.test(label)) return "musica";
  if (/cine/.test(label)) return "cine";
  if (/(teatro|artes-escenicas|danza)/.test(label)) return "teatro";
  if (/(exposicion|exposiciones|museo|museos|artes-visuales)/.test(label)) return "exposiciones";
  if (/(curso|cursos|taller|talleres|formacion)/.test(label)) return "cursos-talleres-campus";
  if (/(deporte|bienestar)/.test(label)) return "deportes";
  if (/(gastronomia|feria|ferias)/.test(label)) return "gastronomia";
  if (/(naturaleza|montana|caminata)/.test(label)) return "naturaleza-montana";
  return "cultura";
}

function isGenericImage(value) {
  if (!value) return false;
  try {
    const url = new URL(String(value), window.location.href);
    const host = url.hostname.replace(/^www\./i, "");
    if (GENERIC_AVATAR_HOSTS.test(host)) return true;
    if (!GENERIC_PROVIDER_HOSTS.test(host)) return false;
    return GENERIC_PROVIDER_PATH.test(decodeURIComponent(url.pathname).toLocaleLowerCase("es"));
  } catch {
    return false;
  }
}

function installCategoryFallback(card, media) {
  if (!(card instanceof HTMLElement) || !(media instanceof HTMLElement)) return;
  const category = categoryIdForCard(card);
  const src = CATEGORY_IMAGES[category] || CATEGORY_IMAGES.cultura;
  const existing = media.querySelector("img");
  if (existing?.dataset?.imageQualityFallback === "true" && existing.getAttribute("src") === src) return;

  const label = String(card.querySelector(".meta")?.textContent || category).trim();
  const image = document.createElement("img");
  image.className = "event-card-photo";
  image.src = src;
  image.alt = `Imagen representativa de la categoría ${label}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.dataset.imageKind = "category-fallback";
  image.dataset.imageQualityFallback = "true";

  media.replaceChildren(image);
  media.classList.remove("event-card-media--placeholder", "has-relevant-image", "has-representative-image");
  media.classList.add("event-card-media--runtime-fallback");
  media.style.setProperty("--event-image", `url("${src}")`);
  media.dataset.categoryPhotoApplied = "true";
  delete media.dataset.representativeImage;
}

function repairCard(card) {
  if (!(card instanceof HTMLElement)) return;
  const media = card.querySelector(".event-card-media");
  if (!(media instanceof HTMLElement)) return;
  const image = media.querySelector("img");

  // Empty/placeholder media are not a valid final state. The base category
  // image is deterministic and must be available even when a source image is
  // absent, invalid or a later optional enhancer did not install one.
  if (media.classList.contains("event-card-media--placeholder") || !(image instanceof HTMLImageElement)) {
    installCategoryFallback(card, media);
    return;
  }
  if (isGenericImage(image.currentSrc || image.src || image.getAttribute("src"))) {
    installCategoryFallback(card, media);
  }
}

function scan() {
  scanQueued = false;
  syncRuntimeIndex();
  document.querySelectorAll('[data-agenda] .event-card').forEach(repairCard);
}

function queueScan() {
  if (scanQueued) return;
  scanQueued = true;
  queueMicrotask(scan);
}

for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:core-ready",
  "vivamos:cards-enriched",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, queueScan);
}

document.addEventListener("error", (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement)) return;
  if (!image.closest('[data-agenda] .event-card')) return;
  queueMicrotask(queueScan);
}, true);

queueScan();
for (const delay of [120, 500, 1200]) setTimeout(queueScan, delay);
