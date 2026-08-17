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
const MY_PLANS_URL = "./mis-planes/";

let eventMap = new Map();
let enhanceQueued = false;

function installAccessStyles() {
  if (document.querySelector("link[data-favorites-access-styles]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./assets/favorites-access.css?v=20260817";
  link.dataset.favoritesAccessStyles = "true";
  document.head.append(link);
}

function eventPageHref(event) {
  const id = String(event?.id || "").trim();
  return id ? new URL(`./evento/${CITY}/${encodeURIComponent(id)}/`, window.location.href).href : null;
}

function favoriteCount() {
  return favoritesForCity(CITY).length;
}

function updateAccessLabel(link) {
  const count = favoriteCount();
  const badge = link.querySelector("[data-favorites-count]");
  const countText = String(count);
  if (badge && badge.textContent !== countText) badge.textContent = countText;
  const label = `Mis planes, ${count} ${count === 1 ? "actividad guardada" : "actividades guardadas"}`;
  if (link.getAttribute("aria-label") !== label) link.setAttribute("aria-label", label);
}

function buildAccessLink() {
  const link = document.createElement("a");
  link.href = MY_PLANS_URL;
  link.className = "favorites-access";
  link.dataset.favoritesAccess = "web";
  const star = document.createElement("span");
  star.className = "favorites-access-star";
  star.setAttribute("aria-hidden", "true");
  star.textContent = "★";
  const label = document.createElement("span");
  label.textContent = "Mis planes";
  const count = document.createElement("span");
  count.className = "favorites-access-count";
  count.dataset.favoritesCount = "true";
  link.append(star, label, count);
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
    const use = link.querySelector("use");
    if (use) use.setAttribute("href", "#icon-star");
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
  const cards = document.querySelectorAll(".event-card[data-event-id], .plan-ahead-card[data-event-id]");
  for (const card of cards) {
    const id = String(card.dataset.eventId || "");
    const event = eventMap.get(id);
    if (!event || card.querySelector(":scope > [data-favorite-toggle]")) continue;
    card.classList.add("favorite-host");
    card.append(buildFavoriteToggle({ city: CITY, event, pageUrl: eventPageHref(event), compact: true }));
  }
}

function installDetailFavorite() {
  const dialog = document.querySelector("[data-detail-dialog]");
  if (!dialog?.open) return;
  const id = new URL(window.location.href).searchParams.get("evento");
  const event = eventMap.get(String(id || ""));
  const actions = dialog.querySelector("[data-detail-actions]");
  if (!event || !actions || actions.querySelector("[data-favorite-toggle]")) return;
  actions.prepend(buildFavoriteToggle({
    city: CITY,
    event,
    pageUrl: eventPageHref(event),
    compact: false,
    className: "favorite-detail-action--web",
  }));
}

function enhanceDynamicUi() {
  enhanceQueued = false;
  installDesktopAccess();
  installMobileAccess();
  installCardFavorites();
  installDetailFavorite();
  syncAccessCounts();
}

function queueEnhance() {
  if (enhanceQueued) return;
  enhanceQueued = true;
  queueMicrotask(enhanceDynamicUi);
}

function refreshFavorites() {
  installDesktopAccess();
  installMobileAccess();
  installCardFavorites();
  installDetailFavorite();
  syncFavoriteButtons(CITY, eventMap);
  syncAccessCounts();
}

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
  window.addEventListener("storage", (event) => {
    if (event.key === FAVORITES_STORAGE_KEY) refreshFavorites();
  });
  window.addEventListener("popstate", queueEnhance);
  refreshFavorites();
}

start();
