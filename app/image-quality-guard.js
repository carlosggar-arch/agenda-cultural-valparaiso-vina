import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";
import {
  generatedEventFallbackImage,
  shouldInstallCategoryFallback,
} from "./image-resolver-core.mjs?v=20260824-owned-images2";

let scanQueued = false;
let indexedRevision = 0;
let eventIndex = new Map();

function syncRuntimeIndex() {
  const snapshot = getAgendaRuntimeSnapshot();
  if (!snapshot) return;
  if (snapshot.revision === indexedRevision && eventIndex.size) return;
  indexedRevision = snapshot.revision;
  eventIndex = new Map(snapshot.events
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));
}

function installGeneratedFallback(card, media) {
  if (!(card instanceof HTMLElement) || !(media instanceof HTMLElement)) return;
  const event = eventIndex.get(String(card?.dataset?.eventId || "").trim());
  const labelHint = String(card.querySelector(".meta")?.textContent || card.querySelector(".event-card-placeholder-label")?.textContent || "").trim();
  const fallback = generatedEventFallbackImage(event, {
    categoryHint: card?.dataset?.category,
    labelHint,
  });
  const src = fallback.url;
  const existing = media.querySelector("img");
  if (existing?.dataset?.imageQualityFallback === "true" && existing.getAttribute("src") === src) return;

  const title = String(event?.title || card.querySelector("h4")?.textContent || "Actividad cultural").trim();
  const image = document.createElement("img");
  image.className = "event-card-photo";
  image.src = src;
  image.alt = `Imagen editorial generada para ${title}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.dataset.imageKind = "generated-fallback";
  image.dataset.imageQualityFallback = "true";

  media.replaceChildren(image);
  media.classList.remove("event-card-media--placeholder", "has-relevant-image", "has-representative-image");
  media.classList.add("event-card-media--runtime-fallback");
  media.style.setProperty("--event-image", `url("${src}")`);
  media.dataset.generatedEventImage = "true";
  delete media.dataset.representativeImage;
}

function repairCard(card) {
  if (!(card instanceof HTMLElement)) return;
  const media = card.querySelector(".event-card-media");
  if (!(media instanceof HTMLElement)) return;
  const image = media.querySelector("img");
  const replace = shouldInstallCategoryFallback({
    placeholder: media.classList.contains("event-card-media--placeholder"),
    hasImage: image instanceof HTMLImageElement,
    currentUrl: image instanceof HTMLImageElement ? (image.currentSrc || image.src || image.getAttribute("src")) : null,
  }, { baseUrl: window.location.href });
  if (replace) installGeneratedFallback(card, media);
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
