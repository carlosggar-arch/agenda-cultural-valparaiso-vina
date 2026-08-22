import { openEventDetail } from "./event-detail.js";
import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";
import {
  canonicalPublicCategoryId,
  publicCategorySymbol,
  publicEventTypeLabel,
} from "./public-category-rules.mjs?v=20260821-shared-taxonomy1";
import {
  buildVenueImagePools,
  looksLikeGenericSchedule,
  relevantEventImageUrl,
  resolveCardImageAfterFailure,
  resolveEventImage,
} from "./image-resolver-core.mjs?v=20260822-single-image1";

const MEDIA_STYLESHEET = "../assets/event-media-layout.css?v=20260816";
const DEFAULT_CONFIG = Object.freeze({ timezone: "UTC", locale: "es" });

let indexedCity = null;
let indexedRevision = 0;
let eventIndex = new Map();
let venueImagePools = new Map();
let featuredIds = new Set();
let enhanceQueued = false;

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function cityId() {
  return String(document.documentElement.dataset.city || "").trim();
}

function cityConfig() {
  return getAgendaRuntimeSnapshot(cityId())?.city || DEFAULT_CONFIG;
}

function primaryCategory(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
}

function categoryId(event) {
  const source = event?.primary_category || event?.categories?.[0] || null;
  return canonicalPublicCategoryId(source) || source?.id || "cultura";
}

function contentTypeLabel(event) {
  return publicEventTypeLabel(event?.event_type);
}

function relevantImageUrl(event) {
  return relevantEventImageUrl(event, { baseUrl: window.location.href });
}

function dateKeyForDate(date, config) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: config.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function dateKeyForValue(value, config) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : dateKeyForDate(date, config);
}

function addDays(dateKey, days) {
  const date = new Date(`${dateKey}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function scheduleRanges(event, config) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = Array.isArray(event?.schedule?.occurrences) && event.schedule.occurrences.length
    ? event.schedule.occurrences
    : event?.schedule?.start
      ? [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }]
      : [];
  return occurrences
    .map((occurrence) => ({
      start: dateKeyForValue(occurrence?.start, config),
      end: dateKeyForValue(occurrence?.end || occurrence?.start, config),
    }))
    .filter((range) => range.start && range.end);
}

function formatDateValue(value, config, { weekday = true, time = true } = {}) {
  if (!value) return null;
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
    const [year, month, day] = text.split("-").map(Number);
    return new Intl.DateTimeFormat(config.locale, {
      timeZone: "UTC",
      weekday: weekday ? "short" : undefined,
      day: "numeric",
      month: "short",
    }).format(new Date(Date.UTC(year, month - 1, day, 12)));
  }
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat(config.locale, {
    timeZone: config.timezone,
    weekday: weekday ? "short" : undefined,
    day: "numeric",
    month: "short",
    ...(time ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  }).format(date);
}

function scheduleLabel(event, config) {
  const opening = String(event?.schedule?.opening_time || "");
  const closing = String(event?.schedule?.closing_time || "");
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const end = event?.schedule?.end;
  if (opening && closing && /^\d{2}:\d{2}$/.test(opening) && /^\d{2}:\d{2}$/.test(closing)) {
    const startDate = start ? formatDateValue(start, config, { time: false }) : null;
    const endKey = end ? dateKeyForValue(end, config) : null;
    const startKey = start ? dateKeyForValue(start, config) : null;
    if (startDate && endKey && startKey && endKey !== startKey) {
      return `${startDate} – ${formatDateValue(end, config, { weekday: false, time: false })} · ${opening}–${closing}`;
    }
    return `${startDate || "Horario de visita"} · ${opening}–${closing}`;
  }
  if (!start) return event?.schedule?.display_text || "Horario por confirmar";
  const startKey = dateKeyForValue(start, config);
  const endKey = end ? dateKeyForValue(end, config) : null;
  if (end && startKey && endKey && endKey !== startKey) {
    return `${formatDateValue(start, config)} – ${formatDateValue(end, config, { weekday: false })}`;
  }
  return formatDateValue(start, config) || event?.schedule?.display_text || "Horario por confirmar";
}

function compactDayLabel(event, config) {
  const ranges = scheduleRanges(event, config);
  const today = dateKeyForDate(new Date(), config);
  if (ranges.some((range) => range.start <= today && range.end >= today)) return { text: "Hoy", today: true };
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const key = dateKeyForValue(start, config);
  if (!key) return null;
  const [year, month, day] = key.split("-").map(Number);
  const text = new Intl.DateTimeFormat(config.locale, { timeZone: "UTC", day: "numeric", month: "short" })
    .format(new Date(Date.UTC(year, month - 1, day, 12)));
  return { text, today: false };
}

function locationLabel(event) {
  const venue = String(event?.location?.venue || "").trim();
  const city = String(event?.location?.city || "").trim();
  if (venue && city && venue.toLocaleLowerCase("es") !== city.toLocaleLowerCase("es")) return `${venue} · ${city}`;
  return venue || city || "Lugar por confirmar";
}

function priceLabel(event) {
  if (event?.price?.is_free === true) return "Gratis";
  const display = String(event?.price?.display_text || "").trim();
  if (display && !/^consultar condiciones$/i.test(display)) return display;
  return event?.price?.is_free === false ? "Actividad pagada" : "Consultar precio";
}

function sourceName(event) {
  return String(event?.source_name || event?.organizer || "").trim();
}

function sourceUrl(event) {
  return safeHttpUrl(event?.source_url || event?.links?.source || event?.links?.official);
}

function meaningfulDescription(event) {
  const description = String(event?.description || "").replace(/\s+/g, " ").trim();
  if (!description || /^actividad publicada en la agenda/i.test(description)) return null;
  if (description.toLocaleLowerCase("es") === String(event?.title || "").trim().toLocaleLowerCase("es")) return null;
  return description.length > 155 ? `${description.slice(0, 152).trimEnd()}…` : description;
}

function contextLabels(event, config) {
  const ranges = scheduleRanges(event, config);
  if (!ranges.length) return [];
  const today = dateKeyForDate(new Date(), config);
  const labels = [];
  if (ranges.some((range) => range.start <= today && range.end >= today)) labels.push("Hoy");
  const soon = addDays(today, 3);
  if (ranges.some((range) => range.start <= today && range.end > today && range.end <= soon)) labels.push("Termina pronto");
  return labels;
}

function featuredScore(event) {
  const status = event?.public_status || {};
  return Number(status.source_official === true) * 12
    + Number(status.information_completeness === "complete") * 8
    + Number(Boolean(event?.links?.registration)) * 4
    + Number(event?.price?.is_free === true);
}

function chooseFeatured(events, config, limit = 3) {
  const today = dateKeyForDate(new Date(), config);
  const ranked = (events || [])
    .filter((event) => event?.public_status?.cancelled !== true)
    .filter((event) => {
      const ranges = scheduleRanges(event, config);
      return !ranges.length || ranges.some((range) => range.end >= today);
    })
    .map((event, order) => ({ event, order, score: featuredScore(event) }))
    .sort((a, b) => b.score - a.score || a.order - b.order);
  const selected = [];
  const categories = new Set();
  for (const item of ranked) {
    const category = categoryId(item.event);
    if (!categories.has(category)) {
      selected.push(item.event.id);
      categories.add(category);
    }
    if (selected.length === limit) return new Set(selected);
  }
  for (const item of ranked) {
    if (selected.length === limit) break;
    if (!selected.includes(item.event.id)) selected.push(item.event.id);
  }
  return new Set(selected);
}

function addTextElement(parent, tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  node.textContent = text;
  parent.append(node);
  return node;
}

function addPlaceholder(media, event, genericSchedule = false) {
  media.classList.add("event-card-media--placeholder");
  media.classList.remove("has-relevant-image", "has-representative-image");
  media.style.removeProperty("--event-image");
  delete media.dataset.representativeImage;
  const category = event?.primary_category || event?.categories?.[0] || null;
  addTextElement(media, "span", "event-card-symbol", publicCategorySymbol(category));
  addTextElement(media, "small", "event-card-placeholder-label", genericSchedule ? "Sin imagen específica" : primaryCategory(event));
  if (genericSchedule) media.dataset.genericScheduleFallback = "true";
}

function installMediaImage(media, event, imageUrl, representative = false) {
  media.classList.remove("event-card-media--placeholder", "has-relevant-image", "has-representative-image");
  media.classList.add(representative ? "has-representative-image" : "has-relevant-image");
  media.style.setProperty("--event-image", `url("${imageUrl.replaceAll('"', "%22")}")`);
  if (representative) media.dataset.representativeImage = "same-venue";
  const image = document.createElement("img");
  image.className = "event-card-photo";
  image.dataset.eventImage = representative ? "representative" : "relevant";
  image.src = imageUrl;
  const venue = String(event?.location?.venue || "el recinto").trim();
  image.alt = representative
    ? `Imagen representativa de ${venue}`
    : String(event?.image?.alt || event?.title || "Imagen de la actividad");
  image.loading = "lazy";
  image.decoding = "async";
  image.addEventListener("error", () => {
    media.replaceChildren();
    media.style.removeProperty("--event-image");
    if (!representative) {
      const fallback = resolveCardImageAfterFailure(event, imageUrl, {
        venueImagePools,
        baseUrl: window.location.href,
      });
      if (fallback.url) {
        installMediaImage(media, event, fallback.url, true);
        return;
      }
    }
    addPlaceholder(media, event, looksLikeGenericSchedule(event));
  }, { once: true });
  media.append(image);
  if (representative) {
    const note = addTextElement(media, "span", "event-card-image-note", "Imagen del recinto");
    note.setAttribute("aria-hidden", "true");
  }
}

function buildMedia(event) {
  const media = document.createElement("div");
  media.className = "event-card-media";
  const resolved = resolveEventImage(event, {
    surface: "card",
    venueImagePools,
    baseUrl: window.location.href,
  });
  if (resolved.url) installMediaImage(media, event, resolved.url, resolved.kind === "representative");
  else addPlaceholder(media, event, resolved.genericSchedule);
  return media;
}

function buildFact(label, value, icon) {
  const row = document.createElement("div");
  row.className = "card-fact";
  const iconNode = addTextElement(row, "span", "card-fact-icon", icon);
  iconNode.setAttribute("aria-hidden", "true");
  const copy = document.createElement("span");
  addTextElement(copy, "span", "sr-only", `${label}: `);
  copy.append(document.createTextNode(value));
  row.append(copy);
  return row;
}

function buildAction(href, label, className) {
  const action = document.createElement("a");
  action.className = `card-action ${className}`;
  action.href = href;
  action.target = "_blank";
  action.rel = "noopener noreferrer";
  action.textContent = label;
  return action;
}

function buildDetailAction(event, presentation) {
  const action = document.createElement("button");
  action.type = "button";
  action.className = "card-action card-action--primary";
  action.dataset.openEvent = event?.id || "event";
  action.textContent = "Ver evento →";
  action.addEventListener("click", () => openEventDetail(event, presentation));
  return action;
}

function renderRichCard(card, event) {
  const config = cityConfig();
  const body = document.createElement("div");
  body.className = "event-card-body";

  const labels = contextLabels(event, config);
  if (featuredIds.has(event.id)) labels.push("No te lo pierdas");
  const uniqueLabels = [...new Set(labels)];
  const day = compactDayLabel(event, config);

  const top = document.createElement("div");
  top.className = "card-meta-row";
  const left = document.createElement("div");
  left.className = "card-meta-left";
  addTextElement(left, "span", "meta", primaryCategory(event));
  const type = contentTypeLabel(event);
  if (type) addTextElement(left, "span", "type-badge", type);
  top.append(left);

  const right = document.createElement("div");
  right.className = "card-meta-right";
  if (day) {
    const badge = addTextElement(right, "span", `card-day-badge${day.today ? " is-today" : ""}`, day.text);
    badge.setAttribute("aria-label", day.today ? "Actividad disponible hoy" : `Fecha: ${day.text}`);
  }
  for (const label of uniqueLabels.filter((label) => label !== "Hoy")) {
    const badge = addTextElement(right, "span", "context-badge", label);
    if (label === "No te lo pierdas") badge.classList.add("context-badge--featured");
    if (label === "Termina pronto") badge.classList.add("context-badge--ending");
  }
  if (right.childElementCount) top.append(right);
  body.append(top);

  addTextElement(body, "h4", "", event?.title || "Actividad sin título");

  const facts = document.createElement("div");
  facts.className = "event-facts";
  facts.append(buildFact("Fecha", scheduleLabel(event, config), "◷"));
  facts.append(buildFact("Lugar", locationLabel(event), "⌖"));
  facts.append(buildFact("Precio", priceLabel(event), event?.price?.is_free === true ? "✓" : "$"));
  body.append(facts);

  const description = meaningfulDescription(event);
  if (description) addTextElement(body, "p", "event-card-description", description);

  const sourceLabel = sourceName(event);
  if (sourceLabel) {
    const source = document.createElement("p");
    source.className = "event-card-source";
    addTextElement(source, "span", "event-card-source-prefix", "Fuente: ");
    const sourceHref = sourceUrl(event);
    if (sourceHref) {
      const link = document.createElement("a");
      link.className = "event-card-source-link";
      link.href = sourceHref;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = sourceLabel;
      source.append(link);
    } else {
      source.append(document.createTextNode(sourceLabel));
    }
    body.append(source);
  }

  const footer = document.createElement("div");
  footer.className = "event-card-footer";
  const trust = document.createElement("div");
  trust.className = "event-card-trust";
  if (event?.public_status?.source_official === true) addTextElement(trust, "span", "trust-chip", "Fuente oficial");
  if (event?.public_status?.registration_open === true) addTextElement(trust, "span", "trust-chip", "Inscripción abierta");
  footer.append(trust);

  const actions = document.createElement("div");
  actions.className = "event-card-actions";
  const official = safeHttpUrl(event?.links?.official || event?.links?.source);
  const registration = safeHttpUrl(event?.links?.registration || event?.links?.tickets);
  if (registration && registration !== official) actions.append(buildAction(registration, "Inscribirme", "card-action--secondary"));
  actions.append(buildDetailAction(event, {
    category: primaryCategory(event),
    type,
    labels: uniqueLabels,
    schedule: scheduleLabel(event, config),
    location: locationLabel(event),
    price: priceLabel(event),
    sourceName: sourceLabel,
    sourceUrl: sourceUrl(event),
    officialUrl: official,
    registrationUrl: registration,
    imageRelevant: Boolean(relevantImageUrl(event)),
  }));
  footer.append(actions);
  body.append(footer);

  card.replaceChildren(buildMedia(event), body);
  card.dataset.cardEnhanced = "true";
  card.classList.toggle("event-card--featured", featuredIds.has(event.id));
}

function syncRuntimeIndex() {
  const currentCity = cityId();
  const snapshot = getAgendaRuntimeSnapshot(currentCity);
  if (!snapshot) return false;
  if (indexedCity === currentCity && indexedRevision === snapshot.revision && eventIndex.size) return true;

  indexedCity = currentCity;
  indexedRevision = snapshot.revision;
  eventIndex = new Map(snapshot.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  venueImagePools = buildVenueImagePools(snapshot.events, { baseUrl: window.location.href });
  featuredIds = chooseFeatured(snapshot.events, snapshot.city || DEFAULT_CONFIG);
  return true;
}

function enhanceAllCards() {
  let changed = 0;
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    const event = eventIndex.get(String(card.dataset.eventId || ""));
    if (!event || card.dataset.cardEnhanced === "true") continue;
    renderRichCard(card, event);
    changed += 1;
  }
  return changed;
}

function runEnhancement() {
  enhanceQueued = false;
  if (!syncRuntimeIndex()) return;
  const changed = enhanceAllCards();
  window.dispatchEvent(new CustomEvent("vivamos:cards-enriched", {
    detail: { cityId: cityId(), changed, revision: indexedRevision },
  }));
}

function scheduleEnhancement() {
  if (enhanceQueued) return;
  enhanceQueued = true;
  queueMicrotask(runEnhancement);
}

function installStylesheet(href, marker) {
  if (document.querySelector(`link[${marker}]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  link.setAttribute(marker, "true");
  document.head.append(link);
}

installStylesheet("./card-experience.css", "data-card-experience");
installStylesheet(MEDIA_STYLESHEET, "data-event-media-layout");
window.addEventListener("vivamos:agenda-data-ready", scheduleEnhancement);
window.addEventListener("vivamos:agenda-rendered", scheduleEnhancement);
scheduleEnhancement();
