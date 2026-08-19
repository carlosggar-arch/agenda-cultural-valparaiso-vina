import { compactScheduleDayLabel, formatSchedule } from "./event-schedule-display.mjs?v=20260819-hours3";
import "./root-combined-filters.js?v=20260817-root-search";
// Plan-ahead remains available for future transversal use, but is intentionally not loaded on the home page.
// Legacy contract marker: ./plan-ahead-web.js?v=20260817
import "./favorites-web.js?v=20260817";
import "./usage-analytics.js?v=20260817-stage32";

const DATASET_URL = "./agenda_web.json";
const MEDIA_STYLESHEET = "./assets/event-media-layout.css?v=20260816b";
const PERMALINK_STYLESHEET = "./assets/event-permalink.css?v=20260817";
const SCHEDULE_OPTIONS = Object.freeze({ locale: "es-CL", timezone: "America/Santiago" });
const REJECTED_EVENT_IDS = new Set(["agenda_968c623b60b70d2976410175"]);
const EDITORIAL_SOCIAL_CUES = [
  /\bsabias que\b/,
  /\bte contamos\b/,
  /\bcuriosidades?\b/,
  /\bdatos (?:de|sobre)\b/,
  /\bdetras de (?:camara|camaras|escena|escenas)\b/,
  /\bmaking of\b/,
  /\btrivia\b/,
  /\bcine dentro del cine\b/,
  /\bdesliza\b/,
  /\bconoce (?:mas|la historia|los detalles|detalles)\b/,
  /\bdescubre (?:mas|la historia|los detalles|detalles)\b/,
];

const CATEGORY_SYMBOLS = Object.freeze({
  musica: "♪",
  cine: "▣",
  teatro: "◒",
  exposiciones: "◇",
  museos: "▥",
  "cursos-talleres": "✦",
  deportes: "●",
  gastronomia: "✺",
  ferias: "◆",
  "naturaleza-montana": "⌁",
});

const MONTH_PATTERN = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre";

function installStylesheet(href, marker) {
  if (document.querySelector(`link[${marker}]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.setAttribute(marker, "true");
  document.head.append(link);
}

function installMediaStyles() {
  installStylesheet(MEDIA_STYLESHEET, "data-event-media-layout");
  installStylesheet(PERMALINK_STYLESHEET, "data-event-permalink-styles");
}

function validHttpUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function sourceUrl(event) {
  return String(event?.source_url || event?.links?.source || event?.links?.official || "");
}

function hasConcreteEventEvidence(event) {
  return Boolean(
    String(event?.location?.venue || "").trim()
    || String(event?.location?.address || "").trim()
    || String(event?.organizer || "").trim()
    || String(event?.links?.tickets || "").trim()
    || String(event?.links?.registration || "").trim()
    || String(event?.registration_requirements || "").trim()
  );
}

function hasEditorialSocialLanguage(event) {
  const text = fold(`${event?.title || ""} ${event?.description || ""}`);
  return EDITORIAL_SOCIAL_CUES.some((pattern) => pattern.test(text));
}

function isEditorialSocialFalsePositive(event) {
  if (REJECTED_EVENT_IDS.has(String(event?.id || ""))) return true;
  if (!sourceUrl(event).includes("instagram.com")) return false;
  if (event?.event_type && event.event_type !== "event") return false;
  if (event?.public_status?.information_completeness === "complete") return false;
  if (hasConcreteEventEvidence(event)) return false;
  return hasEditorialSocialLanguage(event);
}

function categoryId(event) {
  return event?.primary_category?.id || event?.categories?.[0]?.id || "cultura";
}

function categoryLabel(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
}

function eventPageHref(event) {
  const id = String(event?.id || "").trim();
  return id ? `./evento/valparaiso/${encodeURIComponent(id)}/` : null;
}

function looksLikeGenericSchedule(event) {
  if (event?.image?.relevance === "generic_schedule") return true;
  const title = fold(event?.title);
  const description = fold(event?.description);
  if (/\b(agenda|cartelera|programacion|calendario|panoramas?)\b/.test(title)) return true;
  if (new RegExp(`^(?:destino|panoramas?) .+ (?:${MONTH_PATTERN}) 20\\d{2}$`).test(title)) return true;
  const mentions = (String(event?.description || "").match(/@[a-z0-9_.]+/gi) || []).length;
  if (/\beste mes (?:tenemos|incluye|trae|hay)\b/.test(description) && mentions >= 2) return true;
  return false;
}

function relevantImageUrl(event) {
  if (looksLikeGenericSchedule(event)) return null;
  return validHttpUrl(event?.image?.url);
}

function fallbackArtwork(event, { genericSchedule = false } = {}) {
  const placeholder = document.createElement("div");
  placeholder.className = "event-media-fallback";
  placeholder.dataset.theme = categoryId(event);
  placeholder.setAttribute("role", "img");
  placeholder.setAttribute(
    "aria-label",
    genericSchedule
      ? `Imagen general descartada; se usa representación de ${categoryLabel(event)}.`
      : `Ilustración de categoría: ${categoryLabel(event)}.`,
  );
  const symbol = document.createElement("span");
  symbol.className = "event-media-fallback-symbol";
  symbol.setAttribute("aria-hidden", "true");
  symbol.textContent = CATEGORY_SYMBOLS[categoryId(event)] || "✦";
  const label = document.createElement("span");
  label.className = "event-media-fallback-label";
  label.textContent = genericSchedule ? "Sin imagen específica del evento" : categoryLabel(event);
  placeholder.append(symbol, label);
  return placeholder;
}

function removeMediaOverlays(media) {
  if (!media) return;
  media.querySelectorAll(
    "button, .carousel-control, .carousel-control-next, .carousel-control-prev, .swiper-button-next, .swiper-button-prev, [data-media-nav]",
  ).forEach((control) => control.remove());
  media.dataset.mediaOverlayClean = "true";
}

function applyRelevantMedia(media, image, imageUrl, event) {
  removeMediaOverlays(media);
  media.classList.add("has-relevant-image");
  media.classList.remove("event-media--generic");
  media.style.setProperty("--event-image", `url("${imageUrl.replaceAll('"', "%22")}")`);
  image.dataset.eventImage = "relevant";
  image.alt = String(event?.image?.alt || event?.title || "Imagen de la actividad");
}

function installImageTreatment(card, event) {
  const media = card.querySelector(".card-media");
  if (!media) return;
  removeMediaOverlays(media);

  const image = media.querySelector("img");
  const imageUrl = relevantImageUrl(event);
  if (!imageUrl) {
    media.classList.remove("has-relevant-image");
    media.style.removeProperty("--event-image");
    if (looksLikeGenericSchedule(event) && media.dataset.genericFallback !== "true") {
      media.dataset.genericFallback = "true";
      media.classList.add("event-media--generic");
      media.replaceChildren(fallbackArtwork(event, { genericSchedule: true }));
    }
    return;
  }

  if (!image) return;
  applyRelevantMedia(media, image, imageUrl, event);
  if (image.dataset.fallbackBound === "true") return;
  image.dataset.fallbackBound = "true";
  image.addEventListener("error", () => {
    media.classList.remove("has-relevant-image");
    media.style.removeProperty("--event-image");
    media.replaceChildren(fallbackArtwork(event));
  }, { once: true });
}

function compactMetaRow(card, event) {
  const top = card.querySelector(".card-topline");
  if (!top || top.dataset.compactMeta === "true") return;
  const left = document.createElement("span");
  left.className = "card-meta-left";
  while (top.firstChild) left.append(top.firstChild);
  top.append(left);

  const day = compactScheduleDayLabel(event?.schedule, SCHEDULE_OPTIONS);
  if (day) {
    const badge = document.createElement("span");
    badge.className = `card-day-badge${day.today ? " is-today" : ""}`;
    badge.textContent = day.text;
    top.append(badge);
  }
  top.dataset.compactMeta = "true";
}

function installPermalink(card, event) {
  const href = eventPageHref(event);
  if (!href || card.querySelector("[data-event-permalink]")) return;
  const link = document.createElement("a");
  link.className = "event-page-link";
  link.dataset.eventPermalink = "true";
  link.href = href;
  link.textContent = "Ficha completa →";
  link.setAttribute("aria-label", `Abrir ficha completa de ${event?.title || "la actividad"}`);
  link.addEventListener("click", (clickEvent) => clickEvent.stopPropagation());
  card.append(link);
}

function enhanceCard(card, event) {
  installImageTreatment(card, event);
  compactMetaRow(card, event);
  installPermalink(card, event);
  const date = card.querySelector(".card-date");
  if (date) date.textContent = formatSchedule(event?.schedule, SCHEDULE_OPTIONS);
}

function enhanceDetail(event) {
  const dialog = document.querySelector("[data-detail-dialog]");
  if (!dialog?.open) return;
  const terms = [...dialog.querySelectorAll("dt")];
  const term = terms.find((node) => node.textContent.trim() === "Fecha y horario");
  if (term?.nextElementSibling) {
    term.nextElementSibling.textContent = formatSchedule(event?.schedule, SCHEDULE_OPTIONS);
  }
  const media = dialog.querySelector(".card-media");
  removeMediaOverlays(media);
  const image = media?.querySelector("img");
  const imageUrl = relevantImageUrl(event);
  if (media && image && imageUrl) applyRelevantMedia(media, image, imageUrl, event);
  if (media && looksLikeGenericSchedule(event)) {
    media.classList.remove("has-relevant-image");
    media.style.removeProperty("--event-image");
    media.replaceChildren(fallbackArtwork(event, { genericSchedule: true }));
  }
  const actions = dialog.querySelector("[data-detail-actions]");
  const href = eventPageHref(event);
  if (actions && href && !actions.querySelector("[data-event-permalink]")) {
    const link = document.createElement("a");
    link.className = "event-page-link";
    link.dataset.eventPermalink = "true";
    link.href = href;
    link.textContent = "Ver ficha completa →";
    actions.append(link);
  }
}

async function start() {
  installMediaStyles();
  let payload;
  try {
    const response = await fetch(DATASET_URL, { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    payload = await response.json();
  } catch { return; }

  const sourceEvents = payload.events || [];
  const rejectedIds = new Set(
    sourceEvents.filter(isEditorialSocialFalsePositive).map((event) => String(event.id)),
  );
  const events = new Map(
    sourceEvents
      .filter((event) => !rejectedIds.has(String(event.id)))
      .map((event) => [String(event.id), event]),
  );

  const apply = () => {
    document.querySelectorAll(".event-card[data-event-id]").forEach((card) => {
      const id = String(card.dataset.eventId || "");
      if (rejectedIds.has(id)) {
        card.remove();
        return;
      }
      const event = events.get(id);
      if (event) enhanceCard(card, event);
    });
    const total = document.querySelector("[data-total]");
    if (total) total.textContent = String(sourceEvents.length - rejectedIds.size);
    const requested = new URL(window.location.href).searchParams.get("evento");
    if (rejectedIds.has(String(requested || ""))) {
      document.querySelector("[data-detail-dialog]")?.close?.();
      return;
    }
    const event = events.get(String(requested || ""));
    if (event) enhanceDetail(event);
  };

  const observer = new MutationObserver(apply);
  observer.observe(document.body, { childList: true, subtree: true });
  apply();
}

start();
