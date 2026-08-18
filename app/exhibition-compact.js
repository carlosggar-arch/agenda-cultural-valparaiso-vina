import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const STYLE_ID = "exhibition-compact-styles";
const STYLE_HREF = "./exhibition-compact.css?v=20260818-compact2";
const grid = document.querySelector("[data-dated-grid]");
const CITY_REGISTRY = await loadCityRegistry();
const CITIES = CITY_REGISTRY.byId;
const MAX_IMAGES = 4;

const OFFICIAL_VENUE_FALLBACKS = Object.freeze({
  valparaiso: Object.freeze({
    "palacio-vergara": [
      "https://visitavina.munivina.cl/wp-content/uploads/2022/06/Palacio-Vergara-scaled.jpg",
    ],
  }),
});

let queued = false;
let loadedCity = null;
let eventsById = new Map();
let venueImagePools = new Map();
let loadToken = 0;

function ensureStyles() {
  let link = document.getElementById(STYLE_ID);
  if (!link) {
    link = document.createElement("link");
    link.id = STYLE_ID;
    link.rel = "stylesheet";
    document.head.append(link);
  }
  link.href = STYLE_HREF;
}

function currentCityId() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return CITIES[id] ? id : null;
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function venueKey(event) {
  const venueId = String(event?.location?.venue_id || "").trim();
  if (venueId) return venueId;
  return slugify(`${event?.location?.venue || ""}-${event?.location?.city || ""}`);
}

function imageUrl(event) {
  const url = String(event?.image?.url || "").trim();
  return /^https?:\/\//i.test(url) ? url : null;
}

function addUnique(target, value) {
  if (value && !target.includes(value)) target.push(value);
}

function rebuildPools(events) {
  eventsById = new Map();
  venueImagePools = new Map();
  for (const event of events) {
    const id = String(event?.id || "").trim();
    if (id) eventsById.set(id, event);
    const image = imageUrl(event);
    const key = venueKey(event);
    if (!image || !key) continue;
    const pool = venueImagePools.get(key) || [];
    addUnique(pool, image);
    venueImagePools.set(key, pool);
  }
}

async function loadDataset() {
  const cityId = currentCityId();
  if (!cityId) return;
  if (loadedCity === cityId && eventsById.size) return;
  const token = ++loadToken;
  loadedCity = cityId;
  eventsById = new Map();
  venueImagePools = new Map();
  try {
    const response = await fetch(CITIES[cityId].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    if (token !== loadToken || !Array.isArray(dataset.events)) return;
    rebuildPools(dataset.events);
  } catch {
    eventsById = new Map();
    venueImagePools = new Map();
  }
}

function groupIds(card) {
  return String(card.dataset.eventGroup || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
}

function cardEvents(card) {
  return groupIds(card).map((id) => eventsById.get(id)).filter(Boolean);
}

function fallbackImagesForCard(card) {
  const events = cardEvents(card);
  const images = [];
  for (const event of events) addUnique(images, imageUrl(event));

  const first = events[0];
  const key = first ? venueKey(first) : "";
  for (const url of venueImagePools.get(key) || []) addUnique(images, url);

  const cityFallbacks = OFFICIAL_VENUE_FALLBACKS[currentCityId()] || {};
  for (const url of cityFallbacks[key] || []) addUnique(images, url);
  return images.slice(0, MAX_IMAGES);
}

function installCollageImage(collage, url, index) {
  const tile = document.createElement("div");
  tile.className = "exhibition-collage-tile is-fallback-image";
  const img = document.createElement("img");
  img.src = url;
  img.alt = index === 0 ? "Imagen representativa del recinto" : "";
  img.loading = "lazy";
  img.decoding = "async";
  if (index > 0) img.setAttribute("aria-hidden", "true");
  img.addEventListener("error", () => {
    tile.remove();
    collage.dataset.uniformImagePatched = "";
    queueCompact();
  }, { once: true });
  tile.append(img);
  collage.append(tile);
}

function ensureCollage(card, sources) {
  const collage = card.querySelector("[data-exhibition-collage]");
  if (!collage || !sources.length) return;

  const current = [...collage.querySelectorAll(".exhibition-collage-tile img")]
    .map((img) => String(img.currentSrc || img.src || "").trim())
    .filter(Boolean);
  const hasUsableCurrent = current.length > 0 && !collage.querySelector(".exhibition-collage-placeholder");
  if (hasUsableCurrent && current.some((src) => sources.includes(src))) return;

  collage.replaceChildren();
  collage.dataset.count = String(sources.length);
  collage.dataset.uniformImagePatched = "true";
  sources.forEach((url, index) => installCollageImage(collage, url, index));
}

function installRowFallback(media, url) {
  if (!url) return;
  const img = document.createElement("img");
  img.src = url;
  img.alt = "";
  img.loading = "lazy";
  img.decoding = "async";
  img.setAttribute("aria-hidden", "true");
  img.addEventListener("error", () => {
    img.remove();
    media.classList.add("image-error");
    media.classList.remove("is-representative-image");
    delete media.dataset.representativeFallback;
  }, { once: true });
  media.replaceChildren(img);
  media.classList.remove("image-error");
  media.classList.add("is-representative-image");
  media.dataset.representativeFallback = "true";
  media.title = "Imagen representativa del mismo recinto";
}

function ensureRows(card, sources) {
  if (!sources.length) return;
  const rows = [...card.querySelectorAll("[data-grouped-event-id]")];
  rows.forEach((row, index) => {
    const media = row.querySelector(".grouped-exhibition-media");
    if (!media) return;
    const currentImg = media.querySelector("img");
    if (currentImg && !media.classList.contains("image-error")) return;

    const event = eventsById.get(String(row.dataset.groupedEventId || ""));
    const own = event ? imageUrl(event) : null;
    installRowFallback(media, own || sources[index % sources.length]);
  });
}

function patchCard(card) {
  const sources = fallbackImagesForCard(card);
  if (!sources.length) return;
  ensureCollage(card, sources);
  ensureRows(card, sources);
}

async function compactCards() {
  queued = false;
  if (!grid) return;
  await loadDataset();
  for (const card of grid.querySelectorAll(".exhibition-venue-card")) patchCard(card);
}

function queueCompact() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(compactCards);
}

ensureStyles();
queueCompact();

if (grid) {
  new MutationObserver(queueCompact).observe(grid, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "hidden", "src"],
  });
}

new MutationObserver(() => {
  loadedCity = null;
  eventsById = new Map();
  venueImagePools = new Map();
  queueCompact();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
