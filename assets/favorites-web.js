import { FAVORITES_CHANGED_EVENT, FAVORITES_STORAGE_KEY } from "./favorites-core.mjs?v=20260817";
import {
  buildFavoriteToggle,
  buildMyPlansSection,
  installFavoritesStyles,
  syncFavoriteButtons,
} from "./favorites-view.mjs?v=20260817";

const CITY = "valparaiso";
const DATASET_URL = "./agenda_web.json";
const LOCALE = "es-CL";

let eventMap = new Map();
let renderQueued = false;

function eventPageHref(event) {
  const id = String(event?.id || "").trim();
  return id ? new URL(`./evento/${CITY}/${encodeURIComponent(id)}/`, window.location.href).href : null;
}

function installCardFavorites() {
  const cards = document.querySelectorAll(".event-card[data-event-id], .plan-ahead-card[data-event-id]");
  for (const card of cards) {
    if (card.closest("[data-my-plans]")) continue;
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

function renderMyPlans() {
  document.querySelector("[data-my-plans]")?.remove();
  const section = buildMyPlansSection({
    city: CITY,
    locale: LOCALE,
    eventMap,
    eventPageHref,
    onChanged: queueRender,
  });
  const anchor = document.querySelector(".status-panel");
  if (anchor) anchor.insertAdjacentElement("afterend", section);
  else document.querySelector("main")?.prepend(section);
}

function render() {
  renderQueued = false;
  renderMyPlans();
  installCardFavorites();
  installDetailFavorite();
  syncFavoriteButtons(CITY, eventMap);
}

function queueRender() {
  if (renderQueued) return;
  renderQueued = true;
  queueMicrotask(render);
}

async function start() {
  installFavoritesStyles("./assets/favorites.css?v=20260817");
  try {
    const response = await fetch(DATASET_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    eventMap = new Map((payload?.events || []).map((event) => [String(event.id), event]));
  } catch { return; }

  new MutationObserver(queueRender).observe(document.body, { childList: true, subtree: true });
  window.addEventListener(FAVORITES_CHANGED_EVENT, queueRender);
  window.addEventListener("storage", (event) => {
    if (event.key === FAVORITES_STORAGE_KEY) queueRender();
  });
  window.addEventListener("popstate", queueRender);
  queueRender();
}

start();
