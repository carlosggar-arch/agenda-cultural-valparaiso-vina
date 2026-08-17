import {
  emitFavoritesChanged,
  favoriteKey,
  favoritesForCity,
  isFavorite,
  removeFavorite,
  toggleFavorite,
} from "./favorites-core.mjs";

function text(value) {
  return String(value ?? "").trim();
}

export function installFavoritesStyles(href) {
  if (document.querySelector("link[data-favorites-styles]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.dataset.favoritesStyles = "true";
  document.head.append(link);
}

export function eventMoment(event) {
  const value = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  if (!value) return null;
  const raw = text(value);
  const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T12:00:00` : raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function eventLocation(event) {
  const location = event?.location || {};
  const venue = text(location.venue);
  const city = text(location.city);
  return [venue, city].filter(Boolean).filter((value, index, rows) => rows.indexOf(value) === index).join(" · ") || "Lugar por confirmar";
}

export function favoriteSnapshot(city, event, pageUrl) {
  return {
    city,
    id: text(event?.id),
    title: text(event?.title) || "Actividad guardada",
    url: pageUrl,
    savedAt: new Date().toISOString(),
  };
}

function buttonState(button, active, title) {
  button.setAttribute("aria-pressed", String(active));
  button.setAttribute("aria-label", active ? `Quitar ${title} de Mis planes` : `Guardar ${title} en Mis planes`);
  button.title = active ? "Quitar de Mis planes" : "Guardar en Mis planes";
  const star = button.querySelector(".favorite-star");
  if (star) star.textContent = active ? "★" : "☆";
  const label = button.querySelector(".favorite-label");
  if (label) label.textContent = active ? "Guardado" : "Guardar";
}

export function syncFavoriteButton(button, city, event) {
  buttonState(button, isFavorite(city, event?.id), text(event?.title) || "esta actividad");
}

export function buildFavoriteToggle({ city, event, pageUrl, compact = true, className = "" }) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = compact ? `favorite-toggle ${className}`.trim() : `favorite-detail-action ${className}`.trim();
  button.dataset.favoriteToggle = favoriteKey(city, event?.id) || "";
  const star = document.createElement("span");
  star.className = "favorite-star";
  star.setAttribute("aria-hidden", "true");
  button.append(star);
  if (!compact) {
    const label = document.createElement("span");
    label.className = "favorite-label";
    button.append(document.createTextNode(" "), label);
  }
  syncFavoriteButton(button, city, event);
  button.addEventListener("click", (clickEvent) => {
    clickEvent.preventDefault();
    clickEvent.stopPropagation();
    const result = toggleFavorite(favoriteSnapshot(city, event, pageUrl));
    syncFavoriteButton(button, city, event);
    emitFavoritesChanged({ city, id: event?.id, active: result.active });
  });
  return button;
}

export function syncFavoriteButtons(city, eventMap) {
  for (const button of document.querySelectorAll("[data-favorite-toggle]")) {
    const key = text(button.dataset.favoriteToggle);
    if (!key.startsWith(`${city}:`)) continue;
    const id = key.slice(city.length + 1);
    const event = eventMap.get(id);
    if (event) syncFavoriteButton(button, city, event);
  }
}

function formatDate(event, locale) {
  const moment = eventMoment(event);
  if (!moment) return null;
  try {
    return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(moment);
  } catch { return null; }
}

function removeButton(city, favorite, onChanged) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "my-plan-remove";
  button.textContent = "Quitar";
  button.setAttribute("aria-label", `Quitar ${favorite.title || "actividad"} de Mis planes`);
  button.addEventListener("click", () => {
    removeFavorite(city, favorite.id);
    emitFavoritesChanged({ city, id: favorite.id, active: false });
    onChanged?.();
  });
  return button;
}

export function buildMyPlansSection({ city, locale, eventMap, eventPageHref, onChanged }) {
  const favorites = favoritesForCity(city);
  const section = document.createElement("section");
  section.className = "my-plans-section";
  section.id = "mis-planes";
  section.dataset.myPlans = "true";
  section.dataset.city = city;
  section.setAttribute("aria-labelledby", `my-plans-title-${city}`);

  const disclosure = document.createElement("details");
  disclosure.className = "my-plans-disclosure";
  const summary = document.createElement("summary");
  summary.className = "my-plans-summary";

  const icon = document.createElement("span");
  icon.className = "my-plans-summary-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "★";
  const title = document.createElement("strong");
  title.id = `my-plans-title-${city}`;
  title.className = "my-plans-summary-title";
  title.textContent = "Mis planes";
  const count = document.createElement("span");
  count.className = "my-plans-count";
  count.textContent = `${favorites.length} ${favorites.length === 1 ? "guardado" : "guardados"}`;
  count.setAttribute("aria-label", `${favorites.length} actividades guardadas`);
  const chevron = document.createElement("span");
  chevron.className = "my-plans-summary-chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "›";
  summary.append(icon, title, count, chevron);

  const list = document.createElement("div");
  list.className = "my-plans-list";
  if (!favorites.length) {
    const empty = document.createElement("p");
    empty.className = "my-plans-empty";
    empty.textContent = "Pulsa ☆ en una actividad para guardarla aquí.";
    list.append(empty);
  } else {
    const resolved = favorites.map((favorite) => ({ favorite, event: eventMap.get(favorite.id) || null }));
    resolved.sort((left, right) => {
      const leftMoment = eventMoment(left.event)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      const rightMoment = eventMoment(right.event)?.getTime() ?? Number.MAX_SAFE_INTEGER;
      return leftMoment - rightMoment || right.favorite.savedAt.localeCompare(left.favorite.savedAt);
    });

    for (const { favorite, event } of resolved) {
      const article = document.createElement("article");
      article.className = "my-plan-row";
      article.dataset.eventId = favorite.id;

      const when = document.createElement("span");
      when.className = "my-plan-date";
      when.textContent = event && formatDate(event, locale) || "Guardado";

      const main = document.createElement("div");
      main.className = "my-plan-main";
      const rowTitle = document.createElement("strong");
      rowTitle.textContent = event?.title || favorite.title;
      main.append(rowTitle);
      const meta = document.createElement("small");
      meta.textContent = event ? eventLocation(event) : "Ya no aparece en la agenda actual";
      main.append(meta);

      const actions = document.createElement("div");
      actions.className = "my-plan-actions";
      const href = favorite.url || eventPageHref(event || { id: favorite.id });
      if (href) {
        const link = document.createElement("a");
        link.className = "my-plan-action my-plan-action--primary";
        link.href = href;
        link.textContent = "Ver →";
        actions.append(link);
      }
      actions.append(removeButton(city, favorite, onChanged));
      article.append(when, main, actions);
      list.append(article);
    }
  }

  disclosure.append(summary, list);
  section.append(disclosure);
  return section;
}
