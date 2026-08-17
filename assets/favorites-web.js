import {
  FAVORITES_CHANGED_EVENT,
  FAVORITES_STORAGE_KEY,
  favoritesForCity,
} from "./favorites-core.mjs?v=20260817";
import {
  buildFavoriteToggle,
  installFavoritesStyles,
  syncFavoriteButtons,
} from "./favorites-view.mjs?v=20260817";

const CITY = "valparaiso";
const DATASET_URL = "./agenda_web.json";
const MY_PLANS_URL = "./app/mis-planes.html?city=valparaiso";

let eventMap = new Map();
let enhanceQueued = false;

function installAccessStyles() {
  if (document.querySelector("style[data-favorites-access-styles]")) return;
  const style = document.createElement("style");
  style.dataset.favoritesAccessStyles = "true";
  style.textContent = ".favorites-access{display:inline-flex!important;align-items:center!important;gap:.35rem!important;white-space:nowrap}.favorites-access-star{color:#d59a00}.favorites-access-count{display:inline-flex;align-items:center;justify-content:center;min-width:1.4rem;height:1.4rem;padding:0 .35rem;border-radius:999px;background:rgba(6,42,88,.08);font-size:.68rem;font-weight:900}.favorites-mobile-count{position:absolute;top:.18rem;right:calc(50% - 1.15rem);display:inline-flex;align-items:center;justify-content:center;min-width:1.05rem;height:1.05rem;padding:0 .2rem;border-radius:999px;background:#e7b317;color:#082b59;font-size:.5rem;font-weight:900}.mobile-nav a[data-favorites-access]{position:relative}";
  document.head.append(style);
}

function eventPageHref(event) {
  const id = String(event?.id || "").trim();
  return id ? new URL(`./evento/${CITY}/${encodeURIComponent(id)}/`, window.location.href).href : null;
}

function favoriteCount() { return favoritesForCity(CITY).length; }

function updateAccessLabel(link) {
  const count = favoriteCount();
  const badge = link.querySelector("[data-favorites-count]");
  if (badge && badge.textContent !== String(count)) badge.textContent = String(count);
  const aria = `Mis planes, ${count} ${count === 1 ? "actividad guardada" : "actividades guardadas"}`;
  if (link.getAttribute("aria-label") !== aria) link.setAttribute("aria-label", aria);
}

function buildAccessLink() {
  const link = document.createElement("a");
  link.href = MY_PLANS_URL;
  link.className = "favorites-access";
  link.dataset.favoritesAccess = "web";
  link.innerHTML = '<span class="favorites-access-star" aria-hidden="true">★</span><span>Mis planes</span><span class="favorites-access-count" data-favorites-count></span>';
  updateAccessLabel(link);
  return link;
}

function installDesktopAccess() {
  const nav = document.querySelector(".community-links");
  if (!nav || nav.querySelector("[data-favorites-access]")) return;
  nav.prepend(buildAccessLink());
}

function installMobileAccess() {
  const nav = document.querySelector(".mobile-nav");
  if (!nav) return;
  let link = nav.querySelector("[data-favorites-access]");
  if (!link) {
    link = [...nav.querySelectorAll("a")].find((node) => node.getAttribute("href") === "./fuentes.html") || null;
    if (!link) return;
    link.href = MY_PLANS_URL;
    link.dataset.favoritesAccess = "mobile";
    link.querySelector("use")?.setAttribute("href", "#icon-star");
    const label = link.querySelector("span");
    if (label) label.textContent = "Planes";
    const badge = document.createElement("small");
    badge.className = "favorites-mobile-count";
    badge.dataset.favoritesCount = "true";
    link.append(badge);
  }
  updateAccessLabel(link);
}

function syncAccessCounts() {
  for (const link of document.querySelectorAll("[data-favorites-access]")) updateAccessLabel(link);
}

function installCardFavorites() {
  for (const card of document.querySelectorAll(".event-card[data-event-id], .plan-ahead-card[data-event-id]")) {
    const event = eventMap.get(String(card.dataset.eventId || ""));
    if (!event || card.querySelector(":scope > [data-favorite-toggle]")) continue;
    card.classList.add("favorite-host");
    card.append(buildFavoriteToggle({ city: CITY, event, pageUrl: eventPageHref(event), compact: true }));
  }
}

function installDetailFavorite() {
  const dialog = document.querySelector("[data-detail-dialog]");
  if (!dialog?.open) return;
  const event = eventMap.get(String(new URL(window.location.href).searchParams.get("evento") || ""));
  const actions = dialog.querySelector("[data-detail-actions]");
  if (!event || !actions || actions.querySelector("[data-favorite-toggle]")) return;
  actions.prepend(buildFavoriteToggle({ city: CITY, event, pageUrl: eventPageHref(event), compact: false, className: "favorite-detail-action--web" }));
}

function enhanceDynamicUi() {
  enhanceQueued = false;
  installDesktopAccess(); installMobileAccess(); installCardFavorites(); installDetailFavorite(); syncAccessCounts();
}
function queueEnhance() { if (!enhanceQueued) { enhanceQueued = true; queueMicrotask(enhanceDynamicUi); } }
function refreshFavorites() { installDesktopAccess(); installMobileAccess(); installCardFavorites(); installDetailFavorite(); syncFavoriteButtons(CITY, eventMap); syncAccessCounts(); }

async function start() {
  installFavoritesStyles("./assets/favorites.css?v=20260817-compact");
  installAccessStyles();
  try {
    const response = await fetch(DATASET_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    eventMap = new Map((payload?.events || []).map((event) => [String(event.id), event]));
  } catch { return; }
  new MutationObserver(queueEnhance).observe(document.body, { childList: true, subtree: true });
  window.addEventListener(FAVORITES_CHANGED_EVENT, refreshFavorites);
  window.addEventListener("storage", (event) => { if (event.key === FAVORITES_STORAGE_KEY) refreshFavorites(); });
  window.addEventListener("popstate", queueEnhance);
  refreshFavorites();
}
start();
