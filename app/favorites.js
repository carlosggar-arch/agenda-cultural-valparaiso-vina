import { FAVORITES_CHANGED_EVENT, FAVORITES_STORAGE_KEY } from "../assets/favorites-core.mjs?v=20260817";
import {
  buildFavoriteToggle,
  buildMyPlansSection,
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
let renderQueued = false;

function cityId() {
  return CONFIG[document.documentElement.dataset.city] ? document.documentElement.dataset.city : "valparaiso";
}

function eventPageHref(event, city = cityId()) {
  const id = String(event?.id || "").trim();
  return id ? new URL(`../evento/${city}/${encodeURIComponent(id)}/`, window.location.href).href : null;
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
      eventMap = new Map();
      loadedCity = city;
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
    if (card.closest("[data-my-plans]")) continue;
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

function renderMyPlans(city) {
  document.querySelector("[data-my-plans]")?.remove();
  const section = buildMyPlansSection({
    city,
    locale: CONFIG[city].locale,
    eventMap,
    eventPageHref: (event) => eventPageHref(event, city),
    onChanged: queueRender,
  });
  const anchor = document.querySelector("[data-plan-ahead]") || document.querySelector(".agenda");
  if (anchor) anchor.insertAdjacentElement("beforebegin", section);
  else document.querySelector("main")?.append(section);
}

async function render() {
  renderQueued = false;
  const city = cityId();
  if (loadedCity !== city) {
    eventMap = new Map();
    loadedCity = null;
  }
  await ensureDataset();
  if (city !== cityId()) return queueRender();
  cleanOldButtons(city);
  renderMyPlans(city);
  installCardFavorites(city);
  installDetailFavorite(city);
  syncFavoriteButtons(city, eventMap);
}

function queueRender() {
  if (renderQueued) return;
  renderQueued = true;
  queueMicrotask(render);
}

installFavoritesStyles("../assets/favorites.css?v=20260817");
new MutationObserver(queueRender).observe(document.body, { childList: true, subtree: true });
new MutationObserver(() => {
  loadedCity = null;
  eventMap = new Map();
  queueRender();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
window.addEventListener(FAVORITES_CHANGED_EVENT, queueRender);
window.addEventListener("storage", (event) => {
  if (event.key === FAVORITES_STORAGE_KEY) queueRender();
});
queueRender();
