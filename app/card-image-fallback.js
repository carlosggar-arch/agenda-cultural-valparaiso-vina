import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { loadAgendaDataset } from "./data-pipeline.js?v=20260819-pipeline1";

const CATEGORY_PHOTOS = Object.freeze([
  { markers: ["cine"], src: "../assets/categoria-cine.jpg" },
  { markers: ["música", "musica"], src: "../assets/categoria-musica.jpg" },
  { markers: ["teatro", "artes escénicas", "artes escenicas", "danza"], src: "../assets/categoria-teatro.jpg" },
  { markers: ["exposiciones", "exposición", "exposicion", "museos", "museo", "artes visuales"], src: "../assets/categoria-exposiciones.jpg" },
  { markers: ["curso", "taller", "formación", "formacion"], src: "../assets/categoria-talleres.jpg" },
  { markers: ["deporte", "bienestar"], src: "../assets/categoria-deportes.jpg" },
  { markers: ["gastronomía", "gastronomia", "feria"], src: "../assets/categoria-gastronomia.jpg" },
  { markers: ["naturaleza", "montaña", "montana", "caminata"], src: "../assets/categoria-naturaleza.jpg" },
]);

const GENERIC_PROVIDER_HOSTS = /(^|\.)(passline\.com|eventrid\.cl|ticketplus\.(cl|com)|ticketmaster\.cl|puntoticket\.com|ticketpro\.(cl|com|net)|tickets\.cl|ticketera\.cl|ticketfacil\.cl|portaltickets\.cl|goignis\.cl)$/i;
const GENERIC_PROVIDER_PATH = /(?:^|\/)(?:assets?\/(?:img|images?)\/)?(?:icon|logo|favicon|placeholder|default|no[-_]?image|sin[-_]?imagen)(?:[-_.\/]|$)/i;

// Curated correction for the duplicated film listing. The source image below is
// the event-specific artwork already used by the same film in this agenda.
const EVENT_IMAGE_OVERRIDES = Object.freeze({
  "la odisea": "https://www.passline.com/imagenes/eventos/la-odisea-2026-cine-arte-vina-del-mar-544722-rec.jpg",
});

const CITY_REGISTRY = await loadCityRegistry();
const CITY_CONFIG = CITY_REGISTRY.byId;
let indexedCity = null;
let normalizedEvents = [];
let eventIndex = new Map();
let venueImagePools = new Map();
let indexingPromise = null;
let normalizedRepairQueued = false;

function normalize(value) {
  return String(value || "").trim().toLocaleLowerCase("es");
}

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function eventKey(value) {
  return normalize(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\b(?:19|20)\d{2}\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function categoryPhoto(label) {
  const normalized = normalize(label);
  const match = CATEGORY_PHOTOS.find(({ markers }) => markers.some((marker) => normalized.includes(marker)));
  return match?.src || "../assets/categoria-cultura.jpg";
}

function isGenericProviderImage(value) {
  if (!value) return false;
  try {
    const url = new URL(String(value), window.location.href);
    const host = url.hostname.replace(/^www\./i, "");
    if (!GENERIC_PROVIDER_HOSTS.test(host)) return false;
    return GENERIC_PROVIDER_PATH.test(decodeURIComponent(url.pathname).toLocaleLowerCase("es"));
  } catch {
    return false;
  }
}

function safeImageUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), window.location.href);
    if (!["http:", "https:"].includes(url.protocol) || isGenericProviderImage(url.href)) return null;
    return url.href;
  } catch {
    return null;
  }
}

function categoryLabel(event, card = null) {
  return String(event?.primary_category?.label || event?.categories?.[0]?.label || card?.querySelector(".meta")?.textContent || "Cultura").trim() || "Cultura";
}

function categoryId(event) {
  const id = String(event?.primary_category?.id || event?.categories?.[0]?.id || "").trim();
  return id === "museos" ? "exposiciones" : id;
}

function venueKey(event) {
  const venue = fold(event?.location?.venue).replace(/^(?:museo|museum)\s+/, "").trim();
  const city = fold(event?.location?.city || event?.location?.commune);
  return venue ? `${city}|${venue}` : null;
}

function eventSpecificImage(event) {
  if (event?.image?.relevance === "generic_schedule") return null;
  return safeImageUrl(event?.image?.url);
}

function buildVenueImagePools(events) {
  const pools = new Map();
  for (const event of events || []) {
    const key = venueKey(event);
    const url = eventSpecificImage(event);
    if (!key || !url) continue;
    const pool = pools.get(key) || [];
    if (!pool.includes(url)) pool.push(url);
    pools.set(key, pool);
  }
  return pools;
}

function representativeImage(event) {
  const key = venueKey(event);
  return key ? venueImagePools.get(key)?.[0] || null : null;
}

function dateRange(event) {
  const start = String(event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start || "").slice(0, 10);
  const end = String(event?.schedule?.end || event?.schedule?.occurrences?.at?.(-1)?.end || event?.schedule?.occurrences?.at?.(-1)?.start || start).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)) return null;
  return { start, end };
}

function eventImageChoice(event) {
  const specific = eventSpecificImage(event);
  if (specific) return { url: specific, representative: false };
  const sameVenue = representativeImage(event);
  if (sameVenue) return { url: sameVenue, representative: true };
  return { url: categoryPhoto(categoryLabel(event)), representative: false, categoryFallback: true };
}

async function ensureNormalizedIndex() {
  const cityId = String(document.documentElement.dataset.city || CITY_REGISTRY.defaultCityId || "");
  const city = CITY_CONFIG[cityId];
  if (!city) return false;
  if (indexedCity === cityId && eventIndex.size) return true;
  if (indexingPromise) return indexingPromise;
  indexingPromise = (async () => {
    try {
      const result = await loadAgendaDataset(city);
      const events = result?.dataset?.events;
      if (String(document.documentElement.dataset.city || cityId) !== cityId || !Array.isArray(events)) return false;
      indexedCity = cityId;
      normalizedEvents = events;
      eventIndex = new Map(events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
      venueImagePools = buildVenueImagePools(events);
      return true;
    } catch (error) {
      console.warn("¡Vivamos!: no se pudo preparar el índice visual normalizado", error);
      return false;
    } finally {
      indexingPromise = null;
    }
  })();
  return indexingPromise;
}

function setMediaImage(media, url) {
  if (!(media instanceof HTMLElement) || !url) return;
  media.style.setProperty("--event-image", `url("${String(url).replaceAll('"', "%22")}")`);
}

function titleForImage(image) {
  const card = image.closest(".event-card");
  if (card) return card.querySelector("h4")?.textContent?.trim() || "";
  const detail = image.closest(".event-detail-panel");
  return detail?.querySelector(".event-detail-title")?.textContent?.trim() || "";
}

function repairGenericProviderImage(image) {
  if (!(image instanceof HTMLImageElement)) return;
  const requestedSrc = image.getAttribute("src") || image.src;
  if (!isGenericProviderImage(requestedSrc)) return;

  const title = titleForImage(image);
  const override = EVENT_IMAGE_OVERRIDES[eventKey(title)];
  const media = image.closest(".event-card-media, .event-detail-media");

  if (override) {
    image.src = override;
    image.alt = title || image.alt || "Imagen de la actividad";
    image.dataset.imageKind = "event-image-corrected";
    setMediaImage(media, override);
    return;
  }

  // Never show a provider logo/icon as if it were event artwork. Cards without
  // a trustworthy specific image fall back to the category image instead.
  const card = image.closest(".event-card");
  if (card) {
    const label = card.querySelector(".meta")?.textContent?.trim() || "Cultura";
    const fallback = categoryPhoto(label);
    image.src = fallback;
    image.alt = `Imagen representativa de la categoría ${label}`;
    image.dataset.imageKind = "category-fallback";
    setMediaImage(media, fallback);
    return;
  }

  // In the detail dialog, prefer no artwork over misleading provider branding.
  const detailMedia = image.closest(".event-detail-media");
  if (detailMedia) {
    const panel = detailMedia.closest(".event-detail-panel");
    detailMedia.remove();
    panel?.classList.add("event-detail-panel--no-media");
  }
}

function upgradePlaceholder(media) {
  if (!(media instanceof HTMLElement) || media.dataset.categoryPhotoApplied === "true") return;

  const label = media.querySelector(".event-card-placeholder-label")?.textContent?.trim() || "Cultura";
  const image = document.createElement("img");
  image.className = "event-card-photo";
  image.src = categoryPhoto(label);
  image.alt = `Imagen representativa de la categoría ${label}`;
  image.loading = "lazy";
  image.decoding = "async";
  image.dataset.imageKind = "category-fallback";

  image.addEventListener("error", () => {
    media.dataset.categoryPhotoApplied = "failed";
  }, { once: true });

  media.replaceChildren(image);
  media.classList.remove("event-card-media--placeholder");
  media.dataset.categoryPhotoApplied = "true";
}

function upgradeRuntimeCard(card) {
  if (!(card instanceof HTMLElement)) return;
  if (card.dataset.cardEnhanced === "true" || card.dataset.runtimeCardEnhanced === "true") return;
  if (card.querySelector(":scope > .event-card-media, :scope > .event-card-body")) return;
  const event = eventIndex.get(String(card.dataset.eventId || ""));
  if (!event) return;

  const label = categoryLabel(event, card);
  const choice = eventImageChoice(event);
  const media = document.createElement("div");
  media.className = "event-card-media";
  if (choice.categoryFallback) media.classList.add("event-card-media--runtime-fallback");
  const image = document.createElement("img");
  image.className = "event-card-photo";
  image.src = choice.url;
  image.alt = choice.representative
    ? `Imagen representativa de ${String(event?.location?.venue || "el recinto")}`
    : choice.categoryFallback
      ? `Imagen representativa de la categoría ${label}`
      : String(event?.image?.alt || event?.title || "Imagen de la actividad");
  image.loading = "lazy";
  image.decoding = "async";
  image.dataset.imageKind = choice.representative ? "venue-representative" : choice.categoryFallback ? "category-fallback" : "event-image";
  image.addEventListener("error", () => {
    const fallback = categoryPhoto(label);
    image.src = fallback;
    image.alt = `Imagen representativa de la categoría ${label}`;
    image.dataset.imageKind = "category-fallback";
    setMediaImage(media, fallback);
  }, { once: true });
  media.append(image);
  setMediaImage(media, choice.url);
  if (choice.representative) {
    const note = document.createElement("span");
    note.className = "event-card-image-note";
    note.textContent = "Imagen del recinto";
    note.setAttribute("aria-hidden", "true");
    media.append(note);
  }

  const body = document.createElement("div");
  body.className = "event-card-body event-card-body--runtime-fallback";
  while (card.firstChild) body.append(card.firstChild);
  card.replaceChildren(media, body);
  card.dataset.runtimeCardEnhanced = "true";
}

function ensureFilterSentinel(id) {
  let root = document.querySelector("[data-static-exhibition-sentinels]");
  if (!root) {
    root = document.createElement("div");
    root.dataset.staticExhibitionSentinels = "";
    root.hidden = true;
    root.setAttribute("aria-hidden", "true");
    document.body.append(root);
  }
  let sentinel = root.querySelector(`[data-event-id="${CSS.escape(id)}"]`);
  if (sentinel) return sentinel;
  sentinel = document.createElement("span");
  sentinel.className = "event-card static-exhibition-filter-sentinel";
  sentinel.dataset.eventId = id;
  root.append(sentinel);
  return sentinel;
}

function groupedRow(event) {
  const row = document.createElement("article");
  row.className = "grouped-exhibition-item";
  row.dataset.groupedEventId = String(event?.id || "");

  const media = document.createElement("div");
  media.className = "grouped-exhibition-media";
  const choice = eventImageChoice(event);
  const image = document.createElement("img");
  image.src = choice.url;
  image.alt = String(event?.title || "");
  image.loading = "lazy";
  image.decoding = "async";
  image.addEventListener("error", () => { image.src = categoryPhoto("Exposiciones"); }, { once: true });
  media.append(image);

  const copy = document.createElement("div");
  copy.className = "grouped-exhibition-copy";
  const title = document.createElement("strong");
  title.textContent = event?.title || "Exposición sin título";
  const schedule = document.createElement("small");
  schedule.className = "grouped-exhibition-schedule";
  schedule.textContent = String(event?.schedule?.opening_hours?.display_text || event?.schedule?.display_text || "Horario por confirmar");
  copy.append(title, schedule);
  const price = event?.price?.is_free === true ? "Gratis" : String(event?.price?.display_text || "").trim();
  if (price) {
    const priceNode = document.createElement("span");
    priceNode.className = "grouped-exhibition-price";
    priceNode.textContent = price;
    copy.append(priceNode);
  }

  const actions = document.createElement("div");
  actions.className = "grouped-exhibition-actions";
  const href = String(event?.links?.official || event?.links?.source || "").trim();
  if (/^https?:\/\//i.test(href)) {
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Fuente →";
    actions.append(link);
  }

  row.append(media, copy, actions);
  return row;
}

function repairGroupedCompleteness() {
  for (const card of document.querySelectorAll('[data-agenda] .event-card[data-event-group]')) {
    const list = card.querySelector(".exhibition-group-list");
    if (!(list instanceof HTMLElement)) continue;
    const existingIds = String(card.dataset.eventGroup || "").split(",").map((id) => id.trim()).filter(Boolean);
    const existingEvents = existingIds.map((id) => eventIndex.get(id)).filter(Boolean);
    const first = existingEvents[0];
    if (!first || categoryId(first) !== "exposiciones") continue;
    const key = venueKey(first);
    if (!key) continue;

    const ranges = existingEvents.map(dateRange).filter(Boolean);
    if (!ranges.length) continue;
    const commonStart = ranges.reduce((value, range) => value > range.start ? value : range.start, ranges[0].start);
    const commonEnd = ranges.reduce((value, range) => value < range.end ? value : range.end, ranges[0].end);
    const overlapStart = commonStart <= commonEnd ? commonStart : ranges[0].start;
    const overlapEnd = commonStart <= commonEnd ? commonEnd : ranges[0].end;

    const missing = normalizedEvents
      .filter((event) => categoryId(event) === "exposiciones" && venueKey(event) === key)
      .filter((event) => !existingIds.includes(String(event?.id || "")))
      .filter((event) => {
        const range = dateRange(event);
        return range && range.start <= overlapEnd && range.end >= overlapStart;
      })
      .sort((a, b) => String(a?.schedule?.start || "").localeCompare(String(b?.schedule?.start || "")) || String(a?.title || "").localeCompare(String(b?.title || ""), "es"));

    if (!missing.length) continue;
    for (const event of missing) {
      const id = String(event?.id || "").trim();
      if (!id) continue;
      list.append(groupedRow(event));
      existingIds.push(id);
      ensureFilterSentinel(id);
    }
    card.dataset.eventGroup = existingIds.join(",");
    const count = existingIds.length;
    const countNode = card.querySelector("[data-exhibition-visible-count]");
    if (countNode) countNode.textContent = `${count} ${count === 1 ? "exposición disponible" : "exposiciones disponibles"}`;
    const summary = card.querySelector("[data-exhibition-summary]");
    if (summary) summary.textContent = `Ver ${count} ${count === 1 ? "exposición" : "exposiciones"}`;
    card.dataset.normalizedGroupRepaired = "true";
  }
}

async function repairNormalizedPresentation() {
  normalizedRepairQueued = false;
  if (!(await ensureNormalizedIndex())) return;
  document.querySelectorAll('[data-agenda] .event-card[data-event-id]').forEach(upgradeRuntimeCard);
  repairGroupedCompleteness();
}

function queueNormalizedRepair() {
  if (normalizedRepairQueued) return;
  normalizedRepairQueued = true;
  queueMicrotask(() => { void repairNormalizedPresentation(); });
}

function scan() {
  document.querySelectorAll('img[data-event-image="relevant"]').forEach(repairGenericProviderImage);
  document.querySelectorAll(".event-card-media--placeholder").forEach(upgradePlaceholder);
  queueNormalizedRepair();
}

const observer = new MutationObserver(scan);
observer.observe(document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["src"],
});

new MutationObserver(() => {
  indexedCity = null;
  normalizedEvents = [];
  eventIndex = new Map();
  venueImagePools = new Map();
  queueNormalizedRepair();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

scan();
for (const delay of [250, 900, 1800]) setTimeout(queueNormalizedRepair, delay);
