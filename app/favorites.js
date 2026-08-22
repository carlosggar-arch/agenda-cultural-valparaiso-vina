import { FAVORITES_CHANGED_EVENT, FAVORITES_STORAGE_KEY, favoritesForCity } from "../assets/favorites-core.mjs?v=20260817";
import { buildFavoriteToggle, installFavoritesStyles, syncFavoriteButtons } from "../assets/favorites-view.mjs?v=20260817";
import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";

const CITY_REGISTRY = await loadCityRegistry();
const CONFIG = CITY_REGISTRY.byId;

let loadedCity = null;
let loadedRevision = 0;
let eventMap = new Map();
let enhanceQueued = false;
let refreshQueued = false;

function cityId() {
  return CONFIG[document.documentElement.dataset.city]
    ? document.documentElement.dataset.city
    : CITY_REGISTRY.defaultCityId;
}

function eventPageHref(event, city = cityId()) {
  const id = String(event?.id || "").trim();
  return id ? new URL(`../evento/${city}/${encodeURIComponent(id)}/`, location.href).href : null;
}

function installAccessStyles() {
  if (document.querySelector("style[data-favorites-access-styles]")) return;
  const style = document.createElement("style");
  style.dataset.favoritesAccessStyles = "true";
  style.textContent = '.favorites-access--app{display:inline-flex;align-items:center;gap:.35rem;min-height:2.45rem;padding:.48rem .65rem;border:1px solid rgba(23,79,70,.18);border-radius:.75rem;background:#fff;color:inherit;text-decoration:none;font-size:.78rem;font-weight:800;white-space:nowrap}.favorites-access-star{color:#d59a00}.favorites-access-count{display:inline-flex;align-items:center;justify-content:center;min-width:1.4rem;height:1.4rem;padding:0 .35rem;border-radius:999px;background:rgba(6,42,88,.08);font-size:.68rem;font-weight:900}@media(max-width:42rem){.favorites-access--app{padding:.42rem .52rem}.favorites-access-label{display:none}}';
  document.head.append(style);
}

function updateAccess() {
  const city = cityId();
  const link = document.querySelector("[data-favorites-access]");
  if (!link) return;

  const href = `./mis-planes.html?city=${encodeURIComponent(city)}`;
  if (link.getAttribute("href") !== href) link.setAttribute("href", href);

  const count = favoritesForCity(city).length;
  const countText = String(count);
  const badge = link.querySelector("[data-favorites-count]");
  // Keep observer-driven enhancement idempotent. Replacing the same text node
  // creates a childList mutation and can otherwise feed the observer forever.
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
    link.className = "favorites-access--app";
    link.dataset.favoritesAccess = "app";
    link.innerHTML = '<span class="favorites-access-star" aria-hidden="true">★</span><span class="favorites-access-label">Mis planes</span><span class="favorites-access-count" data-favorites-count></span>';
    actions.prepend(link);
  }
  updateAccess();
}

function syncRuntimeDataset() {
  const city = cityId();
  const snapshot = getAgendaRuntimeSnapshot(city);
  if (!snapshot || !Array.isArray(snapshot.events)) return false;
  if (loadedCity === city && loadedRevision === snapshot.revision) return true;

  eventMap = new Map(
    snapshot.events
      .map((event) => [String(event?.id || "").trim(), event])
      .filter(([id]) => id),
  );
  loadedCity = city;
  loadedRevision = Number(snapshot.revision || 0);
  return true;
}

function cleanOldButtons(city) {
  for (const button of document.querySelectorAll("[data-favorite-toggle]")) {
    const key = String(button.dataset.favoriteToggle || "");
    if (key && !key.startsWith(`${city}:`)) button.remove();
  }
}

function installCardFavorites(city) {
  for (const card of document.querySelectorAll(".event-card[data-event-id], .plan-ahead-card[data-event-id]")) {
    const event = eventMap.get(String(card.dataset.eventId || ""));
    if (!event || card.querySelector(":scope > [data-favorite-toggle]")) continue;
    card.classList.add("favorite-host");
    card.append(buildFavoriteToggle({
      city,
      event,
      pageUrl: eventPageHref(event, city),
      compact: true,
    }));
  }
}

function installDetailFavorite(city) {
  const dialog = document.querySelector("dialog[data-event-detail]");
  if (!dialog?.open) return;
  const event = eventMap.get(String(dialog.dataset.eventDetail || ""));
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

function enhance() {
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
  queueMicrotask(enhance);
}

function refresh() {
  refreshQueued = false;
  const city = cityId();
  installAccess();

  if (!syncRuntimeDataset()) {
    cleanOldButtons(city);
    return;
  }
  if (city !== cityId()) {
    queueRefresh();
    return;
  }
  cleanOldButtons(city);
  installCardFavorites(city);
  installDetailFavorite(city);
  syncFavoriteButtons(city, eventMap);
  updateAccess();
}

function queueRefresh() {
  if (refreshQueued) return;
  refreshQueued = true;
  queueMicrotask(refresh);
}

installFavoritesStyles("../assets/favorites.css?v=20260817-compact");
installAccessStyles();
new MutationObserver(queueEnhance).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => {
  loadedCity = null;
  loadedRevision = 0;
  eventMap = new Map();
  queueRefresh();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
addEventListener("vivamos:agenda-data-ready", queueRefresh);
addEventListener(FAVORITES_CHANGED_EVENT, queueRefresh);
addEventListener("storage", (event) => {
  if (event.key === FAVORITES_STORAGE_KEY) queueRefresh();
});
queueRefresh();
