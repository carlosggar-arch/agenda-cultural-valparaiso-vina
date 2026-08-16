const DATASET_URL = "./agenda_web.json";
const MEDIA_STYLESHEET = "./assets/event-media-layout.css?v=20260816";

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

function installMediaStyles() {
  if (document.querySelector('link[data-event-media-layout]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = MEDIA_STYLESHEET;
  link.dataset.eventMediaLayout = "true";
  document.head.append(link);
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

function categoryId(event) {
  return event?.primary_category?.id || event?.categories?.[0]?.id || "cultura";
}

function categoryLabel(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
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

function applyRelevantMedia(media, image, imageUrl, event) {
  media.classList.add("has-relevant-image");
  media.classList.remove("event-media--generic");
  media.style.setProperty("--event-image", `url("${imageUrl.replaceAll('"', "%22")}")`);
  image.dataset.eventImage = "relevant";
  image.alt = String(event?.image?.alt || event?.title || "Imagen de la actividad");
}

function installImageTreatment(card, event) {
  const media = card.querySelector(".card-media");
  if (!media) return;

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

function visitHours(event) {
  const schedule = event?.schedule || {};
  const opening = String(schedule.opening_time || "").match(/^\d{2}:\d{2}$/)?.[0];
  const closing = String(schedule.closing_time || "").match(/^\d{2}:\d{2}$/)?.[0];
  return opening && closing ? `${opening}–${closing}` : null;
}

function dateOnly(value) {
  const text = String(value || "");
  if (!text) return null;
  const datePart = text.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(datePart)) return null;
  const [year, month, day] = datePart.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12));
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

function dateKey(value) {
  const text = String(value || "");
  if (!text) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Santiago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function todayKey() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Santiago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function shortDayLabel(event) {
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const end = event?.schedule?.end || start;
  const startKey = dateKey(start);
  const endKey = dateKey(end);
  const today = todayKey();
  if (startKey && endKey && startKey <= today && endKey >= today) return { text: "Hoy", today: true };
  if (!startKey) return null;
  const [year, month, day] = startKey.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12));
  const text = new Intl.DateTimeFormat("es-CL", { timeZone: "UTC", day: "numeric", month: "short" }).format(date);
  return { text, today: false };
}

function compactMetaRow(card, event) {
  const top = card.querySelector(".card-topline");
  if (!top || top.dataset.compactMeta === "true") return;
  const left = document.createElement("span");
  left.className = "card-meta-left";
  while (top.firstChild) left.append(top.firstChild);
  top.append(left);

  const day = shortDayLabel(event);
  if (day) {
    const badge = document.createElement("span");
    badge.className = `card-day-badge${day.today ? " is-today" : ""}`;
    badge.textContent = day.text;
    top.append(badge);
  }
  top.dataset.compactMeta = "true";
}

function visitScheduleLabel(event) {
  const hours = visitHours(event);
  if (!hours) return null;
  const startDate = dateOnly(event?.schedule?.start);
  const endDate = dateOnly(event?.schedule?.end);
  if (startDate && endDate && String(event.schedule.start).slice(0, 10) !== String(event.schedule.end).slice(0, 10)) {
    return `${startDate} – ${endDate} · ${hours}`;
  }
  return `${startDate || "Horario de visita"} · ${hours}`;
}

function enhanceCard(card, event) {
  installImageTreatment(card, event);
  compactMetaRow(card, event);
  const label = visitScheduleLabel(event);
  if (label) {
    const date = card.querySelector(".card-date");
    if (date) date.textContent = label;
  }
}

function enhanceDetail(event) {
  const label = visitScheduleLabel(event);
  const dialog = document.querySelector("[data-detail-dialog]");
  if (!dialog?.open) return;
  if (label) {
    const terms = [...dialog.querySelectorAll("dt")];
    const term = terms.find((node) => node.textContent.trim() === "Fecha y horario");
    if (term?.nextElementSibling) term.nextElementSibling.textContent = label;
  }
  const media = dialog.querySelector(".card-media");
  const image = media?.querySelector("img");
  const imageUrl = relevantImageUrl(event);
  if (media && image && imageUrl) applyRelevantMedia(media, image, imageUrl, event);
  if (media && looksLikeGenericSchedule(event)) {
    media.classList.remove("has-relevant-image");
    media.style.removeProperty("--event-image");
    media.replaceChildren(fallbackArtwork(event, { genericSchedule: true }));
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
  const events = new Map((payload.events || []).map((event) => [String(event.id), event]));

  const apply = () => {
    document.querySelectorAll(".event-card[data-event-id]").forEach((card) => {
      const event = events.get(card.dataset.eventId);
      if (event) enhanceCard(card, event);
    });
    const requested = new URL(window.location.href).searchParams.get("evento");
    const event = events.get(String(requested || ""));
    if (event) enhanceDetail(event);
  };

  const observer = new MutationObserver(apply);
  observer.observe(document.body, { childList: true, subtree: true });
  apply();
}

start();
