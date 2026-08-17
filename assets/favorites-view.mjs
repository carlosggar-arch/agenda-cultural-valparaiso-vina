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
    return new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "short" }).format(moment);
  } catch { return null; }
}

export function buildMyPlansSection({ city, locale, eventMap, eventPageHref, onChanged }) {
  const section = document.createElement("section");
  section.className = "my-plans-section";
  section.id = "mis-planes";
  section.dataset.myPlans = "true";
  section.dataset.city = city;
  section.setAttribute("aria-labelledby", `my-plans-title-${city}`);

  const inner = document.createElement("div");
  inner.className = "my-plans-inner";
  const heading = document.createElement("header");
  heading.className = "my-plans-heading";
  const copy = document.createElement("div");
  copy.className = "my-plans-heading-copy";
  const eyebrow = document.createElement("p");
  eyebrow.className = "my-plans-eyebrow";
  eyebrow.textContent = "Tu agenda personal";
  const title = document.createElement("h2");
  title.id = `my-plans-title-${city}`;
  title.textContent = "★ Mis planes";
  const intro = document.createElement("p");
  intro.textContent = "Guarda actividades y encuéntralas aquí aunque cierres la aplicación o el navegador.";
  copy.append(eyebrow, title, intro);
  const count = document.createElement("span");
  count.className = "my-plans-count";
  heading.append(copy, count);
  inner.append(heading);

  const favorites = favoritesForCity(city);
  count.textContent = String(favorites.length);
  count.setAttribute("aria-label", `${favorites.length} actividades guardadas`);

  if (!favorites.length) {
    const empty = document.createElement("div");
    empty.className = "my-plans-empty";
    const strong = document.createElement("strong");
    strong.textContent = "Aún no tienes planes guardados";
    const paragraph = document.createElement("p");
    paragraph.textContent = "Pulsa ☆ en cualquier actividad para añadirla aquí.";
    empty.append(strong, paragraph);
    inner.append(empty);
    section.append(inner);
    return section;
  }

  const resolved = favorites.map((favorite) => ({ favorite, event: eventMap.get(favorite.id) || null }));
  resolved.sort((left, right) => {
    const leftMoment = eventMoment(left.event)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    const rightMoment = eventMoment(right.event)?.getTime() ?? Number.MAX_SAFE_INTEGER;
    return leftMoment - rightMoment || right.favorite.savedAt.localeCompare(left.favorite.savedAt);
  });

  const grid = document.createElement("div");
  grid.className = "my-plans-grid";
  for (const { favorite, event } of resolved) {
    const card = document.createElement("article");
    card.className = "my-plan-card";
    card.dataset.eventId = favorite.id;

    const cardTitle = document.createElement("h3");
    cardTitle.textContent = event?.title || favorite.title;
    card.append(cardTitle);

    const meta = document.createElement("p");
    meta.className = "my-plan-meta";
    meta.textContent = [event && formatDate(event, locale), event && eventLocation(event)].filter(Boolean).join(" · ") || "Actividad guardada";
    card.append(meta);

    if (!event) {
      const stale = document.createElement("p");
      stale.className = "my-plan-status";
      stale.textContent = "Ya no aparece en la agenda actual; conservamos tu guardado para que puedas revisarlo o quitarlo.";
      card.append(stale);
    }

    const remove = buildFavoriteToggle({
      city,
      event: event || { id: favorite.id, title: favorite.title },
      pageUrl: favorite.url || eventPageHref({ id: favorite.id }),
      compact: true,
    });
    card.classList.add("favorite-host");
    card.append(remove);

    const actions = document.createElement("div");
    actions.className = "my-plan-actions";
    const href = favorite.url || eventPageHref(event || { id: favorite.id });
    if (href) {
      const link = document.createElement("a");
      link.className = "my-plan-action my-plan-action--primary";
      link.href = href;
      link.textContent = "Ver ficha →";
      actions.append(link);
    }
    const removeText = document.createElement("button");
    removeText.type = "button";
    removeText.className = "my-plan-action";
    removeText.textContent = "Quitar";
    removeText.addEventListener("click", () => {
      removeFavorite(city, favorite.id);
      emitFavoritesChanged({ city, id: favorite.id, active: false });
      onChanged?.();
    });
    actions.append(removeText);
    card.append(actions);
    grid.append(card);
  }
  inner.append(grid);
  section.append(inner);
  return section;
}
