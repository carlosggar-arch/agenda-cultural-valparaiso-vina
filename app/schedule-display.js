import { formatSchedule } from "../assets/event-schedule-display.mjs?v=20260819-hours3";
import { loadAgendaDataset } from "./data-pipeline.js?v=20260819-pipeline1";
import { gijonLocationForEvent, scheduleForGijonEvent } from "./gijon-venue-hours.js";

const CITY_CONFIG = Object.freeze({
  valparaiso: {
    id: "valparaiso",
    dataset: "../agenda_web.json",
    locale: "es-CL",
    timezone: "America/Santiago",
  },
  gijon: {
    id: "gijon",
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
  return formatSchedule(schedule, activeConfig);
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

function visibleCopyText(copy) {
  if (!copy) return "";
  const full = String(copy.textContent || "");
  const sr = String(copy.querySelector(".sr-only")?.textContent || "");
  return (sr && full.startsWith(sr) ? full.slice(sr.length) : full).trim();
}

function replaceFactValue(row, value, marker = "scheduleDisplay") {
  const copy = row?.querySelector(":scope > span:last-child");
  if (!copy) return;
  if (visibleCopyText(copy) === value && copy.dataset[marker] === value) return;
  const sr = copy.querySelector(".sr-only");
  copy.replaceChildren();
  if (sr) copy.append(sr);
  copy.append(document.createTextNode(value));
  copy.dataset[marker] = value;
}

function replaceSimpleCardSchedule(card, value) {
  // Base app cards use h4 + p for the schedule and the following p for location.
  const copy = card.querySelector(":scope > h4 + p");
  if (!copy) return false;
  if (copy.textContent.trim() === value && copy.dataset.scheduleDisplay === value) return true;
  copy.textContent = value;
  copy.dataset.scheduleDisplay = value;
  return true;
}

function replaceSimpleCardLocation(card, value) {
  const schedule = card.querySelector(":scope > h4 + p");
  const copy = schedule?.nextElementSibling;
  if (!copy || copy.tagName !== "P") return false;
  if (copy.textContent.trim() === value && copy.dataset.locationDisplay === value) return true;
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
  if (scheduleFact) replaceFactValue(scheduleFact, schedule, "scheduleDisplay");
  else replaceSimpleCardSchedule(card, schedule);

  const locationFact = facts.find((row) =>
    row.querySelector(".sr-only")?.textContent.trim().startsWith("Lugar:"),
  );
  if (locationFact) replaceFactValue(locationFact, location, "locationDisplay");
  else replaceSimpleCardLocation(card, location);

  enhanceSource(card, event);
}

function enhanceGroupedExhibition(row) {
  const event = eventIndex.get(String(row.dataset.groupedEventId || ""));
  const copy = row.querySelector(".grouped-exhibition-copy > small");
  if (!event || !copy) return;
  const value = scheduleForDisplay(event);
  if (copy.textContent.trim() === value && copy.dataset.scheduleDisplay === value) return;
  copy.textContent = value;
  copy.dataset.scheduleDisplay = value;
}

function replaceDetailFact(dialog, label, value) {
  const fact = [...dialog.querySelectorAll(".event-detail-fact")].find((row) =>
    row.querySelector("strong")?.textContent.trim() === label,
  );
  const copy = fact?.querySelector("span:last-child");
  if (!copy) return;
  if (copy.textContent.trim() === value && copy.dataset.enhancedDisplay === value) return;
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
  document.querySelectorAll("[data-grouped-event-id]").forEach(enhanceGroupedExhibition);
  document.querySelectorAll("dialog[data-event-detail]").forEach(enhanceDetail);
  bodyObserver.takeRecords();
}

function queueApply() {
  if (applyQueued) return;
  applyQueued = true;
  queueMicrotask(apply);
}

const bodyObserver = new MutationObserver((mutations) => {
  if (mutations.some((mutation) => mutation.addedNodes.length || mutation.removedNodes.length || mutation.type === "characterData")) {
    queueApply();
  }
});
bodyObserver.observe(document.body, { childList: true, subtree: true, characterData: true });

async function load(city = currentCity()) {
  const config = CITY_CONFIG[city] || CITY_CONFIG.valparaiso;
  const generation = ++loadGeneration;
  activeCityId = city;
  activeConfig = config;
  eventIndex = new Map();

  try {
    // Use the exact same pure data pipeline as app-core. Reading the raw dataset
    // here can overwrite a normalized multi-session card with only its first raw
    // occurrence (for example 13:00 while hiding the 18:00 session).
    const result = await loadAgendaDataset(config);
    if (generation !== loadGeneration || activeCityId !== city) return;
    eventIndex = new Map((result.dataset?.events || []).map((event) => [String(event.id), event]));
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
