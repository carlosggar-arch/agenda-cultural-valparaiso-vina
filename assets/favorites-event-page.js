import { FAVORITES_CHANGED_EVENT, FAVORITES_STORAGE_KEY } from "./favorites-core.mjs?v=20260817";
import { buildFavoriteToggle, installFavoritesStyles, syncFavoriteButton } from "./favorites-view.mjs?v=20260817";

function start() {
  const body = document.body;
  const city = String(body?.dataset.city || "");
  const id = String(body?.dataset.eventId || "");
  const title = document.querySelector("h1")?.textContent?.trim() || document.title.replace(/ · Agenda Cultural$/, "");
  const host = document.querySelector("[data-favorite-event-host]") || document.querySelector(".event-actions");
  if (!city || !id || !host) return;

  installFavoritesStyles("../../../assets/favorites.css?v=20260817");
  const event = { id, title };
  const existing = host.querySelector("[data-favorite-event]");
  const button = buildFavoriteToggle({
    city,
    event,
    pageUrl: window.location.href,
    compact: false,
    className: "event-action event-favorite-action",
  });
  button.dataset.favoriteEvent = "true";
  if (existing) existing.replaceWith(button);
  else host.prepend(button);

  const sync = () => syncFavoriteButton(button, city, event);
  window.addEventListener(FAVORITES_CHANGED_EVENT, sync);
  window.addEventListener("storage", (storageEvent) => {
    if (storageEvent.key === FAVORITES_STORAGE_KEY) sync();
  });
}

start();
