import {
  FAVORITES_CHANGED_EVENT,
  FAVORITES_STORAGE_KEY,
  favoritesForCity,
} from "../assets/favorites-core.mjs?v=20260817";
import {
  buildFavoriteToggle,
  installFavoritesStyles,
  syncFavoriteButtons,
} from "../assets/favorites-view.mjs?v=20260817";

const CONFIG = Object.freeze({
  valparaiso: { dataset: "../agenda_web.json", locale: "es-CL" },
  gijon: { dataset: "./data/gijon/agenda_web.json", locale: "es-ES" },
});

let loadedCity = null;
let eventMap = new Map();
let loadPromise = null;
let enhanceQueued = false;
let refreshQueued = false;

function installAccessStyles() {
  if (document.querySelector("link[data-favorites-access-styles]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "../assets/favorites-access.css?v=20260817";
  link.dataset.favoritesAccessStyles = "true";
  document.head.append(link);
}

function cityId() {
  return CONFIG[document.documentElement.dataset.city] ? document.documentElement.dataset.city : "valparaiso";
}

function eventPageHref(event, city = cityId()) {
  const id = String(event?.id || "").trim();
  return id ? new URL(`../evento/${city}/${encodeURIComponent(id)}/`, window.location.href).href : null;
}

function myPlansHref(city = cityId()) {
  return `./mis-planes.html?city=${encodeURIComponent(city)}`;
}

function favoriteCount(city = cityId()) {
  return favoritesForCity(city).length;
}

function updateAccess() {
  const city = cityId();
  const link = document.querySelector("[data-favorites-access]");
  if (!link) return;
  const href = myPlansHref(city);
  if (link.getAttribute("href") !== href) link.href = href;
  const count = favoriteCount(city);
  const countText = String(count);
  const badge = link.querySelector("[data-favorites-count]");
  if (badge && badge.textContent !== countText) badge.textContent = countText;
  const label = `Mis planes, ${count} ${count === 1 ? "actividad guardada" : "actividades guardadas"}`;
  if (link.getAttribute("aria-label") !== label) link.setAttribute("aria-label", label);
}

function installAccess() {
  const actions = document.querySelector(".header-actions");
  if (!actions) return;
  let link = actions.querySelector("[data-favorites-access]");
  if (!link) {
    link = document.createElement("a");
    link.className = "favorites-access favorites-access--app";
    link.dataset.favoritesAccess = "app";
    const star = document.createElement("span");
    star.className = "favorites-access-star";
    star.setAttribute("aria-hidden", "true");
    star.textContent = "★";
    const label = document.createElement("span");
    label.className = "favorites-access-label";
    label.textContent = "Mis planes";
    const count = document.createElement("span");
    count.className = "favorites-access-count";
    count.dataset.favoritesCount = "true";
    link.append(star, label, count);
    actions.prepend(link);
  }
  updateAccess();
}

async function ensureDataset() {
  const city = cityId();
  if (loadedCity === city && eventMap.size) return;
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    try {
      const response = await fetch(CONFIG[city].dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return;
      const payload = await response.json();
      if (city !== cityId()) return;
      eventMap = new Map((payload?.events || []).map((event) => [String(event.id), event]));
      loadedCity = city;
    } catch {
      if (city === cityId()) {
        eventMap = new Map();
        loadedCity = city;
      }
    } finally {
      loadPromise = null;
    }
  })();
  return loadPromise;
}

function cleanOldButtons(city) {
  for (const button of document.querySelectorAll("[data-favorite-toggle]")) {
    const key = String(button.dataset.favoriteToggle || "");
    if (key && !key.startsWith(`${city}:`)) button.remove();
  }
}

function installCardFavorites(city) {
  const cards = document.querySelectorAll(".event-card[data-event-id], .plan-ahead-card[data-event-id]");
  for (const card of cards) {
    const id = String(card.dataset.eventId || "");
    const event = eventMap.get(id);
    if (!event || card.querySelector(":scope > [data-favorite-toggle]")) continue;
    card.classList.add("favorite-host");
    card.append(buildFavoriteToggle({ city, event, pageUrl: eventPageHref(event, city), compact: true }));
  }
}

function installDetailFavorite(city) {
  const dialog = document.querySelector("dialog[data-event-detail]");
  if (!dialog?.open) return;
  const id = String(dialog.dataset.eventDetail || "");
  const event = eventMap.get(id);
  const actions = dialog.querySelector(".event-detail-actions");
  if (!event || !actions || actions.querySelector("[data-favorite-toggle]")) return;
  actions.prepend(buildFavoriteToggle({
    city,
    event,
    pageUrl: eventPageHref(event, city),
    compact: false,
    className: "event-detail-action event-detail-action--secondary",
  }));
}

function enhanceDynamicUi() {
  enhanceQueued = false;
  const city = cityId();
  if (loadedCity !== city) return;
  installAccess();
  cleanOldButtons(city);
  installCardFavorites(city);
  installDetailFavorite(city);
}

function queueEnhance() {
  if (enhanceQueued) return;
  enhanceQueued = true;
  queueMicrotask(enhanceDynamicUi);
}

async function refreshFavorites() {
  refreshQueued = false;
  const city = cityId();
  if (loadedCity !== city) {
    eventMap = new Map();
    loadedCity = null;
  }
  await ensureDataset();
  if (city !== cityId()) return queueRefresh();
  installAccess();
  cleanOldButtons(city);
  installCardFavorites(city);
  installDetailFavorite(city);
  syncFavoriteButtons(city, eventMap);
  updateAccess();
}

function queueRefresh() {
  if (refreshQueued) return;
  refreshQueued = true;
  queueMicrotask(refreshFavorites);
}

installFavoritesStyles("../assets/favorites.css?v=20260817-compact");
installAccessStyles();
new MutationObserver(queueEnhance).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => {
  loadedCity = null;
  eventMap = new Map();
  queueRefresh();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
window.addEventListener(FAVORITES_CHANGED_EVENT, queueRefresh);
window.addEventListener("storage", (event) => {
  if (event.key === FAVORITES_STORAGE_KEY) queueRefresh();
});
queueRefresh();
