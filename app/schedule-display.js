import { formatSchedule } from "../assets/event-schedule-display.mjs?v=20260817-hours";
import { scheduleForGijonEvent } from "./gijon-venue-hours.js";

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

function enhanceCard(card) {
  const event = eventIndex.get(String(card.dataset.eventId || ""));
  if (!event) return;
  const schedule = scheduleForDisplay(event);

  const fact = [...card.querySelectorAll(".card-fact")].find((row) =>
    row.querySelector(".sr-only")?.textContent.trim().startsWith("Fecha:"),
  );
  if (fact) replaceFactValue(fact, schedule);
  else replaceSimpleCardSchedule(card, schedule);
}

function enhanceDetail(dialog) {
  const id = String(dialog.dataset.eventDetail || "");
  const event = eventIndex.get(id);
  if (!event) return;
  const schedule = scheduleForDisplay(event);
  const fact = [...dialog.querySelectorAll(".event-detail-fact")].find((row) =>
    row.querySelector("strong")?.textContent.trim() === "Fecha y horario",
  );
  const value = fact?.querySelector("span:last-child");
  if (!value || value.dataset.scheduleDisplay === schedule) return;
  value.textContent = schedule;
  value.dataset.scheduleDisplay = schedule;
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
