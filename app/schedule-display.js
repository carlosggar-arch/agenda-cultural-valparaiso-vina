import { formatSchedule } from "../assets/event-schedule-display.mjs?v=20260817-hours";
import { gijonLocationForEvent, scheduleForGijonEvent } from "./gijon-venue-hours.js";

const CITY_CONFIG = Object.freeze({
  valparaiso: {
    dataset: "../agenda_web.json",
    locale: "es-CL",
    timezone: "America/Santiago",
  },
  gijon: {
    dataset: "./data/gijon/agenda_web.json",
    locale: "es-ES",
    timezone: "Europe/Madrid",
  },
});

let eventIndex = new Map();
let activeConfig = CITY_CONFIG.valparaiso;
let activeCityId = "valparaiso";
let applyQueued = false;
let loadGeneration = 0;

function currentCity() {
  const fromDocument = document.documentElement.dataset.city;
  if (CITY_CONFIG[fromDocument]) return fromDocument;
  try {
    const stored = localStorage.getItem("agenda-cultural-city");
    if (CITY_CONFIG[stored]) return stored;
  } catch { /* ignore storage restrictions */ }
  return "valparaiso";
}

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function stripMediaControls(root = document) {
  root.querySelectorAll(".card-media, .event-card-media, .event-detail-media").forEach((media) => {
    media.querySelectorAll(
      "button, .carousel-control, .carousel-control-next, .carousel-control-prev, .swiper-button-next, .swiper-button-prev, [data-media-nav]",
    ).forEach((control) => control.remove());
    if (media.dataset.mediaOverlayClean !== "true") media.dataset.mediaOverlayClean = "true";
  });
}

function scheduleForDisplay(event) {
  const schedule = activeCityId === "gijon" ? scheduleForGijonEvent(event) : event?.schedule;
  if (!schedule) return "Horario por confirmar";

  const openingText = String(schedule?.opening_hours?.display_text || "").trim();
  if (!openingText) return formatSchedule(schedule, activeConfig);

  // The shared formatter supports simple opening/closing pairs. Gijón's official
  // directories frequently publish split and seasonal hours, so preserve that
  // richer verified text verbatim and combine it with the event date range.
  const dateOnlySchedule = { ...schedule, opening_hours: null, opening_time: null, closing_time: null };
  const dateText = formatSchedule(dateOnlySchedule, activeConfig);
  if (!dateText || dateText === "Horario por confirmar") return openingText;
  return `${dateText} · ${openingText}`;
}

function locationForDisplay(event) {
  const location = activeCityId === "gijon" ? gijonLocationForEvent(event) : { ...(event?.location || {}) };
  const venue = String(location?.venue || "").trim();
  const city = String(location?.city || "").trim();
  const foldedVenue = venue
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
  if (activeCityId === "gijon" && ["gijon/xixon", "gijon", "xixon"].includes(foldedVenue)) {
    return "Lugar por confirmar";
  }
  if (venue && city && venue.toLocaleLowerCase("es") !== city.toLocaleLowerCase("es")) return `${venue} · ${city}`;
  return venue || city || "Lugar por confirmar";
}

function replaceFactValue(row, value) {
  const copy = row?.querySelector(":scope > span:last-child");
  if (!copy || copy.dataset.scheduleDisplay === value) return;
  const sr = copy.querySelector(".sr-only");
  copy.replaceChildren();
  if (sr) copy.append(sr);
  copy.append(document.createTextNode(value));
  copy.dataset.scheduleDisplay = value;
}

function replaceSimpleCardSchedule(card, value) {
  // Base app cards use h4 + p for the schedule and the following p for location.
  const copy = card.querySelector(":scope > h4 + p");
  if (!copy || copy.dataset.scheduleDisplay === value) return false;
  copy.textContent = value;
  copy.dataset.scheduleDisplay = value;
  return true;
}

function replaceSimpleCardLocation(card, value) {
  const schedule = card.querySelector(":scope > h4 + p");
  const copy = schedule?.nextElementSibling;
  if (!copy || copy.tagName !== "P" || copy.dataset.locationDisplay === value) return false;
  copy.textContent = value;
  copy.dataset.locationDisplay = value;
  return true;
}

function enhanceSource(card, event) {
  if (activeCityId !== "gijon" || event?.source_id !== "gijon_opendata_events") return;
  const official = safeHttpUrl(event?.links?.official || event?.links?.source);
  if (!official) return;
  const link = card.querySelector(".event-card-source-link");
  if (!link) return;
  const label = "Ayuntamiento de Gijón/Xixón · ficha oficial ↗";
  if (link.href !== official) link.href = official;
  if (link.textContent !== label) link.textContent = label;
  const prefix = card.querySelector(".event-card-source-prefix");
  if (prefix && prefix.textContent !== "Fuente oficial: ") prefix.textContent = "Fuente oficial: ";
}

function enhanceCard(card) {
  const event = eventIndex.get(String(card.dataset.eventId || ""));
  if (!event) return;
  const schedule = scheduleForDisplay(event);
  const location = locationForDisplay(event);

  const facts = [...card.querySelectorAll(".card-fact")];
  const scheduleFact = facts.find((row) =>
    row.querySelector(".sr-only")?.textContent.trim().startsWith("Fecha:"),
  );
  if (scheduleFact) replaceFactValue(scheduleFact, schedule);
  else replaceSimpleCardSchedule(card, schedule);

  const locationFact = facts.find((row) =>
    row.querySelector(".sr-only")?.textContent.trim().startsWith("Lugar:"),
  );
  if (locationFact) replaceFactValue(locationFact, location);
  else replaceSimpleCardLocation(card, location);

  enhanceSource(card, event);
}

function replaceDetailFact(dialog, label, value) {
  const fact = [...dialog.querySelectorAll(".event-detail-fact")].find((row) =>
    row.querySelector("strong")?.textContent.trim() === label,
  );
  const copy = fact?.querySelector("span:last-child");
  if (!copy || copy.dataset.enhancedDisplay === value) return;
  copy.textContent = value;
  copy.dataset.enhancedDisplay = value;
}

function enhanceDetail(dialog) {
  const id = String(dialog.dataset.eventDetail || "");
  const event = eventIndex.get(id);
  if (!event) return;
  replaceDetailFact(dialog, "Fecha y horario", scheduleForDisplay(event));
  replaceDetailFact(dialog, "Lugar", locationForDisplay(event));

  if (activeCityId === "gijon" && event?.source_id === "gijon_opendata_events") {
    replaceDetailFact(dialog, "Fuente", "Ayuntamiento de Gijón/Xixón · Agenda de Eventos");
  }
}

function apply() {
  applyQueued = false;
  stripMediaControls();
  document.querySelectorAll(".event-card[data-event-id]").forEach(enhanceCard);
  document.querySelectorAll("dialog[data-event-detail]").forEach(enhanceDetail);
  bodyObserver.takeRecords();
}

function queueApply() {
  if (applyQueued) return;
  applyQueued = true;
  queueMicrotask(apply);
}

const bodyObserver = new MutationObserver((mutations) => {
  if (mutations.some((mutation) => mutation.addedNodes.length || mutation.removedNodes.length)) queueApply();
});
bodyObserver.observe(document.body, { childList: true, subtree: true });

async function load(city = currentCity()) {
  const config = CITY_CONFIG[city] || CITY_CONFIG.valparaiso;
  const generation = ++loadGeneration;
  activeCityId = city;
  activeConfig = config;
  eventIndex = new Map();

  try {
    const response = await fetch(config.dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const payload = await response.json();
    if (generation !== loadGeneration || activeCityId !== city) return;
    eventIndex = new Map((payload.events || []).map((event) => [String(event.id), event]));
  } catch { return; }

  queueApply();
}

new MutationObserver(() => {
  const city = currentCity();
  if (city !== activeCityId) load(city);
}).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});

load();
