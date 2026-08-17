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
  valparaiso: { dataset: "../agenda_web.json" },
  gijon: { dataset: "./data/gijon/agenda_web.json" },
});
let loadedCity = null;
let eventMap = new Map();
let loadPromise = null;
let enhanceQueued = false;
let refreshQueued = false;

function installAccessStyles() {
  if (document.querySelector("style[data-favorites-access-styles]")) return;
  const style = document.createElement("style");
  style.dataset.favoritesAccessStyles = "true";
  style.textContent = '.favorites-access--app{display:inline-flex;align-items:center;gap:.35rem;min-height:2.45rem;padding:.48rem .65rem;border:1px solid rgba(23,79,70,.18);border-radius:.75rem;background:#fff;color:inherit;text-decoration:none;font-size:.78rem;font-weight:800;white-space:nowrap}.favorites-access-star{color:#d59a00}.favorites-access-count{display:inline-flex;align-items:center;justify-content:center;min-width:1.4rem;height:1.4rem;padding:0 .35rem;border-radius:999px;background:rgba(6,42,88,.08);font-size:.68rem;font-weight:900}@media(max-width:42rem){.favorites-access--app{padding:.42rem .52rem}.favorites-access-label{display:none}}';
  document.head.append(style);
}
function cityId() { return CONFIG[document.documentElement.dataset.city] ? document.documentElement.dataset.city : "valparaiso"; }
function eventPageHref(event, city = cityId()) { const id = String(event?.id || "").trim(); return id ? new URL(`../evento/${city}/${encodeURIComponent(id)}/`, window.location.href).href : null; }
function myPlansHref(city = cityId()) { return `./mis-planes.html?city=${encodeURIComponent(city)}`; }
function updateAccess() {
  const city = cityId();
  const link = document.querySelector("[data-favorites-access]");
  if (!link) return;
  link.href = myPlansHref(city);
  const count = favoritesForCity(city).length;
  const badge = link.querySelector("[data-favorites-count]");
  if (badge && badge.textContent !== String(count)) badge.textContent = String(count);
  link.setAttribute("aria-label", `Mis planes, ${count} ${count === 1 ? "actividad guardada" : "actividades guardadas"}`);
}
function installAccess() {
  const actions = document.querySelector(".header-actions");
  if (!actions) return;
  let link = actions.querySelector("[data-favorites-access]");
  if (!link) {
    link = document.createElement("a");
    link.className = "favorites-access--app";
    link.dataset.favoritesAccess = "app";
    link.innerHTML = '<span class="favorites-access-star" aria-hidden="true">★</span><span class="favorites-access-label">Mis planes</span><span class="favorites-access-count" data-favorites-count></span>';
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
      eventMap = new Map((payload?.events || []).map((event) => [String(event.id), event])); loadedCity = city;
    } catch { if (city === cityId()) { eventMap = new Map(); loadedCity = city; } }
    finally { loadPromise = null; }
  })();
  return loadPromise;
}
function cleanOldButtons(city) { for (const button of document.querySelectorAll("[data-favorite-toggle]")) { const key = String(button.dataset.favoriteToggle || ""); if (key && !key.startsWith(`${city}:`)) button.remove(); } }
function installCardFavorites(city) {
  for (const card of document.querySelectorAll(".event-card[data-event-id], .plan-ahead-card[data-event-id]")) {
    const event = eventMap.get(String(card.dataset.eventId || ""));
    if (!event || card.querySelector(":scope > [data-favorite-toggle]")) continue;
    card.classList.add("favorite-host"); card.append(buildFavoriteToggle({ city, event, pageUrl: eventPageHref(event, city), compact: true }));
  }
}
function installDetailFavorite(city) {
  const dialog = document.querySelector("dialog[data-event-detail]"); if (!dialog?.open) return;
  const event = eventMap.get(String(dialog.dataset.eventDetail || "")); const actions = dialog.querySelector(".event-detail-actions");
  if (!event || !actions || actions.querySelector("[data-favorite-toggle]")) return;
  actions.prepend(buildFavoriteToggle({ city, event, pageUrl: eventPageHref(event, city), compact: false, className: "event-detail-action event-detail-action--secondary" }));
}
function enhanceDynamicUi() { enhanceQueued = false; const city = cityId(); if (loadedCity !== city) return; installAccess(); cleanOldButtons(city); installCardFavorites(city); installDetailFavorite(city); }
function queueEnhance() { if (!enhanceQueued) { enhanceQueued = true; queueMicrotask(enhanceDynamicUi); } }
async function refreshFavorites() {
  refreshQueued = false; const city = cityId();
  if (loadedCity !== city) { eventMap = new Map(); loadedCity = null; }
  await ensureDataset(); if (city !== cityId()) return queueRefresh();
  installAccess(); cleanOldButtons(city); installCardFavorites(city); installDetailFavorite(city); syncFavoriteButtons(city, eventMap); updateAccess();
}
function queueRefresh() { if (!refreshQueued) { refreshQueued = true; queueMicrotask(refreshFavorites); } }

installFavoritesStyles("../assets/favorites.css?v=20260817-compact");
installAccessStyles();
new MutationObserver(queueEnhance).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => { loadedCity = null; eventMap = new Map(); queueRefresh(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
window.addEventListener(FAVORITES_CHANGED_EVENT, queueRefresh);
window.addEventListener("storage", (event) => { if (event.key === FAVORITES_STORAGE_KEY) queueRefresh(); });
queueRefresh();
