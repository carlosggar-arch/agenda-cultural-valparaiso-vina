const STORAGE_KEY = "agenda-cultural-city";

const CITY_PRESENTATION = Object.freeze({
  valparaiso: {
    dataset: "../agenda_web.json",
    timezone: "America/Santiago",
    locale: "es-CL",
  },
  gijon: {
    dataset: "./data/gijon/agenda_web.json",
    timezone: "Europe/Madrid",
    locale: "es-ES",
  },
});

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

let indexedCity = null;
let eventIndex = new Map();
let featuredIds = new Set();
let enhanceQueued = false;
let indexingPromise = null;

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
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return CITY_PRESENTATION[saved] ? saved : null;
  } catch {
    return null;
  }
}

function cityConfig() {
  return CITY_PRESENTATION[cityId()] || CITY_PRESENTATION.valparaiso;
}

function primaryCategory(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
}

function categoryId(event) {
  return event?.primary_category?.id || event?.categories?.[0]?.id || "cultura";
}

function contentTypeLabel(event) {
  if (event?.event_type === "program") return "Programa";
  if (event?.event_type === "flexible_offer") return "Actividad disponible";
  if (event?.event_type === "course") return "Curso";
  if (event?.event_type === "workshop") return "Taller";
  return null;
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
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const end = event?.schedule?.end;
  if (!start) return event?.schedule?.display_text || "Horario por confirmar";
  const startKey = dateKeyForValue(start, config);
  const endKey = end ? dateKeyForValue(end, config) : null;
  if (end && startKey && endKey && endKey !== startKey) {
    return `${formatDateValue(start, config)} – ${formatDateValue(end, config, { weekday: false })}`;
  }
  return formatDateValue(start, config) || event?.schedule?.display_text || "Horario por confirmar";
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

function buildMedia(event) {
  const media = document.createElement("div");
  media.className = "event-card-media";
  const imageUrl = safeHttpUrl(event?.image?.url);
  if (imageUrl) {
    const image = document.createElement("img");
    image.className = "event-card-photo";
    image.src = imageUrl;
    image.alt = String(event?.image?.alt || event?.title || "Imagen de la actividad");
    image.loading = "lazy";
    image.decoding = "async";
    image.addEventListener("error", () => {
      image.remove();
      media.classList.add("event-card-media--placeholder");
      addTextElement(media, "span", "event-card-symbol", CATEGORY_SYMBOLS[categoryId(event)] || "✦");
      addTextElement(media, "small", "event-card-placeholder-label", primaryCategory(event));
    }, { once: true });
    media.append(image);
  } else {
    media.classList.add("event-card-media--placeholder");
    addTextElement(media, "span", "event-card-symbol", CATEGORY_SYMBOLS[categoryId(event)] || "✦");
    addTextElement(media, "small", "event-card-placeholder-label", primaryCategory(event));
  }
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

function renderRichCard(card, event) {
  const config = cityConfig();
  const body = document.createElement("div");
  body.className = "event-card-body";

  const top = document.createElement("div");
  top.className = "card-meta-row";
  addTextElement(top, "span", "meta", primaryCategory(event));
  const type = contentTypeLabel(event);
  if (type) addTextElement(top, "span", "type-badge", type);
  body.append(top);

  const labels = contextLabels(event, config);
  if (featuredIds.has(event.id)) labels.push("No te lo pierdas");
  if (labels.length) {
    const context = document.createElement("div");
    context.className = "card-context-row";
    for (const label of [...new Set(labels)]) {
      const badge = addTextElement(context, "span", "context-badge", label);
      if (label === "No te lo pierdas") badge.classList.add("context-badge--featured");
      if (label === "Hoy") badge.classList.add("context-badge--today");
      if (label === "Termina pronto") badge.classList.add("context-badge--ending");
    }
    body.append(context);
  }

  addTextElement(body, "h4", "", event?.title || "Actividad sin título");

  const facts = document.createElement("div");
  facts.className = "event-facts";
  facts.append(buildFact("Fecha", scheduleLabel(event, config), "◷"));
  facts.append(buildFact("Lugar", locationLabel(event), "⌖"));
  facts.append(buildFact("Precio", priceLabel(event), event?.price?.is_free === true ? "✓" : "$"));
  body.append(facts);

  const description = meaningfulDescription(event);
  if (description) addTextElement(body, "p", "event-card-description", description);

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
  if (official) actions.append(buildAction(official, "Ver evento →", "card-action--primary"));
  else if (registration) actions.append(buildAction(registration, "Ver detalles →", "card-action--primary"));
  footer.append(actions);
  body.append(footer);

  card.replaceChildren(buildMedia(event), body);
  card.dataset.cardEnhanced = "true";
  card.classList.toggle("event-card--featured", featuredIds.has(event.id));
}

function enhanceAllCards() {
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    const event = eventIndex.get(card.dataset.eventId);
    if (!event) continue;
    if (card.dataset.cardEnhanced === "true") continue;
    renderRichCard(card, event);
  }
}

async function indexCurrentCity() {
  const currentCity = cityId();
  if (!currentCity) return;
  if (indexedCity === currentCity && eventIndex.size) return;
  if (indexingPromise) return indexingPromise;
  const config = CITY_PRESENTATION[currentCity];
  indexingPromise = (async () => {
    try {
      const response = await fetch(config.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return;
      const dataset = await response.json();
      if (!Array.isArray(dataset?.events)) return;
      indexedCity = currentCity;
      eventIndex = new Map(dataset.events.map((event) => [String(event.id), event]));
      featuredIds = chooseFeatured(dataset.events, config);
    } catch (error) {
      console.warn("Agenda Cultural: no se pudo enriquecer la presentación de tarjetas", error);
    } finally {
      indexingPromise = null;
    }
  })();
  return indexingPromise;
}

async function runEnhancement() {
  enhanceQueued = false;
  const currentCity = cityId();
  if (!currentCity) return;
  if (indexedCity !== currentCity) {
    indexedCity = null;
    eventIndex = new Map();
    featuredIds = new Set();
  }
  await indexCurrentCity();
  enhanceAllCards();
}

function scheduleEnhancement() {
  if (enhanceQueued) return;
  enhanceQueued = true;
  queueMicrotask(runEnhancement);
}

function installStylesheet() {
  if (document.querySelector('link[data-card-experience]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./card-experience.css";
  link.dataset.cardExperience = "true";
  document.head.append(link);
}

installStylesheet();
const observer = new MutationObserver(scheduleEnhancement);
observer.observe(document.body, { childList: true, subtree: true, characterData: true });
scheduleEnhancement();
