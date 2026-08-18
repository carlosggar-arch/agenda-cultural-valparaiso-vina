import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const STYLE_ID = "exhibition-compact-styles";
const STYLE_HREF = "./exhibition-compact.css?v=20260818-compact8";
const datedGrid = document.querySelector("[data-dated-grid]");
const grids = [...document.querySelectorAll(".event-grid")];
const CITY_REGISTRY = await loadCityRegistry();
const CITIES = CITY_REGISTRY.byId;
const MAX_IMAGES = 6;
const EQUALIZE_BREAKPOINT = 561;
const ROW_TOP_TOLERANCE = 4;

const OFFICIAL_VENUE_FALLBACKS = Object.freeze({
  valparaiso: Object.freeze({
    "palacio-vergara": [
      "https://visitavina.munivina.cl/wp-content/uploads/2022/06/Palacio-Vergara-scaled.jpg",
    ],
  }),
});

let queued = false;
let equalizeQueued = false;
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

function failedSources(media) {
  return new Set(String(media.dataset.failedImageSources || "")
    .split("|")
    .map((value) => value.trim())
    .filter(Boolean));
}

function rememberFailed(media, url) {
  if (!url) return;
  const failed = failedSources(media);
  failed.add(url);
  media.dataset.failedImageSources = [...failed].join("|");
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
    queueEqualization();
  }, { once: true });
  tile.append(img);
  collage.append(tile);
}

function ensureCollage(card, sources) {
  const collage = card.querySelector("[data-exhibition-collage]");
  if (!collage || !sources.length) return;

  const currentTiles = [...collage.querySelectorAll(".exhibition-collage-tile")]
    .filter((tile) => !tile.classList.contains("image-error"));
  const current = currentTiles
    .map((tile) => tile.querySelector("img"))
    .filter(Boolean)
    .map((img) => String(img.currentSrc || img.src || "").trim())
    .filter(Boolean);
  const hasUsableCurrent = current.length > 0 && !collage.querySelector(".exhibition-collage-placeholder");
  if (hasUsableCurrent) return;

  collage.replaceChildren();
  collage.dataset.count = String(sources.length);
  collage.dataset.uniformImagePatched = "true";
  sources.slice(0, 4).forEach((url, index) => installCollageImage(collage, url, index));
}

function installRowFallback(media, sources, startIndex = 0) {
  const failed = failedSources(media);
  const candidates = sources.filter((url) => url && !failed.has(url));
  if (!candidates.length) {
    media.replaceChildren();
    media.classList.add("image-error", "image-fallback-artwork");
    return;
  }

  const url = candidates[startIndex % candidates.length];
  const img = document.createElement("img");
  img.src = url;
  img.alt = "";
  img.loading = "lazy";
  img.decoding = "async";
  img.setAttribute("aria-hidden", "true");
  img.addEventListener("load", () => {
    media.classList.remove("image-error", "image-fallback-artwork");
    media.classList.add("is-representative-image");
    media.dataset.representativeFallback = "true";
    media.title = "Imagen representativa del mismo recinto";
  }, { once: true });
  img.addEventListener("error", () => {
    rememberFailed(media, url);
    img.remove();
    media.classList.add("image-error");
    installRowFallback(media, sources, startIndex + 1);
  }, { once: true });

  media.replaceChildren(img);
  media.classList.remove("image-error", "image-fallback-artwork");
}

function ensureRows(card, sources) {
  const rows = [...card.querySelectorAll("[data-grouped-event-id]")];
  rows.forEach((row, index) => {
    const media = row.querySelector(".grouped-exhibition-media");
    if (!media) return;

    const currentImg = media.querySelector("img");
    if (currentImg && !media.classList.contains("image-error")) return;

    if (currentImg) {
      const failedUrl = String(currentImg.currentSrc || currentImg.src || "").trim();
      rememberFailed(media, failedUrl);
    }

    const rotated = sources.length
      ? [...sources.slice(index % sources.length), ...sources.slice(0, index % sources.length)]
      : [];
    installRowFallback(media, rotated, 0);
  });
}

function patchCard(card) {
  const sources = fallbackImagesForCard(card);
  ensureCollage(card, sources);
  ensureRows(card, sources);
}

function visibleDirectCards(grid) {
  return [...grid.children].filter((node) => {
    if (!(node instanceof HTMLElement) || !node.classList.contains("event-card") || node.hidden) return false;
    const style = getComputedStyle(node);
    return style.display !== "none" && style.visibility !== "hidden";
  });
}

function clearEqualHeight(card) {
  card.style.removeProperty("min-height");
}

function visualRows(cards) {
  const rows = [];
  for (const card of cards) {
    const top = card.getBoundingClientRect().top;
    let row = rows.find((candidate) => Math.abs(candidate.top - top) <= ROW_TOP_TOLERANCE);
    if (!row) {
      row = { top, cards: [] };
      rows.push(row);
    }
    row.cards.push(card);
  }
  return rows;
}

function equalizeGrid(grid) {
  const cards = visibleDirectCards(grid);
  cards.forEach(clearEqualHeight);

  if (window.innerWidth < EQUALIZE_BREAKPOINT || cards.length < 2) return;

  /* Equalize only cards that actually share a visual row. The previous global
     maximum made every card in a large city as tall as the single tallest card
     anywhere in the grid, producing huge blank panels in Gijón. */
  void grid.offsetHeight;
  for (const row of visualRows(cards)) {
    if (row.cards.length < 2) continue;
    let commonHeight = 0;
    for (const card of row.cards) {
      commonHeight = Math.max(commonHeight, Math.ceil(card.getBoundingClientRect().height));
    }
    if (!commonHeight) continue;
    for (const card of row.cards) {
      card.style.setProperty("min-height", `${commonHeight}px`, "important");
    }
  }
}

function equalizeAllGrids() {
  equalizeQueued = false;
  for (const grid of grids) equalizeGrid(grid);
}

function queueEqualization() {
  if (equalizeQueued) return;
  equalizeQueued = true;
  requestAnimationFrame(() => requestAnimationFrame(equalizeAllGrids));
}

async function compactCards() {
  queued = false;
  if (datedGrid) {
    await loadDataset();
    for (const card of datedGrid.querySelectorAll(".exhibition-venue-card")) patchCard(card);
  }
  queueEqualization();
}

function queueCompact() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(compactCards);
}

ensureStyles();
queueCompact();

const gridObserver = new MutationObserver(() => {
  queueCompact();
  queueEqualization();
});
for (const grid of grids) {
  gridObserver.observe(grid, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "hidden", "src"],
  });
}

window.addEventListener("resize", queueEqualization, { passive: true });
if (document.fonts?.ready) document.fonts.ready.then(queueEqualization).catch(() => {});

new MutationObserver(() => {
  loadedCity = null;
  eventsById = new Map();
  venueImagePools = new Map();
  queueCompact();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });