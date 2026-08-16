import { formatSchedule } from "../assets/event-schedule-display.mjs";

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
let applyQueued = false;

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
    media.dataset.mediaOverlayClean = "true";
  });
}

function replaceFactValue(row, value) {
  const copy = row?.querySelector(":scope > span:last-child");
  if (!copy) return;
  const sr = copy.querySelector(".sr-only");
  copy.replaceChildren();
  if (sr) copy.append(sr);
  copy.append(document.createTextNode(value));
}

function enhanceCard(card) {
  const event = eventIndex.get(String(card.dataset.eventId || ""));
  if (!event) return;
  const schedule = formatSchedule(event.schedule, activeConfig);
  const fact = [...card.querySelectorAll(".card-fact")].find((row) =>
    row.querySelector(".sr-only")?.textContent.trim().startsWith("Fecha:"),
  );
  if (fact) replaceFactValue(fact, schedule);
}

function enhanceDetail(dialog) {
  const id = String(dialog.dataset.eventDetail || "");
  const event = eventIndex.get(id);
  if (!event) return;
  const schedule = formatSchedule(event.schedule, activeConfig);
  const fact = [...dialog.querySelectorAll(".event-detail-fact")].find((row) =>
    row.querySelector("strong")?.textContent.trim() === "Fecha y horario",
  );
  const value = fact?.querySelector("span:last-child");
  if (value) value.textContent = schedule;
}

function apply() {
  applyQueued = false;
  stripMediaControls();
  document.querySelectorAll(".event-card[data-event-id]").forEach(enhanceCard);
  document.querySelectorAll("dialog[data-event-detail]").forEach(enhanceDetail);
}

function queueApply() {
  if (applyQueued) return;
  applyQueued = true;
  queueMicrotask(apply);
}

async function load() {
  const city = currentCity();
  activeConfig = CITY_CONFIG[city] || CITY_CONFIG.valparaiso;
  try {
    const response = await fetch(activeConfig.dataset, { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    const payload = await response.json();
    eventIndex = new Map((payload.events || []).map((event) => [String(event.id), event]));
  } catch { return; }

  const observer = new MutationObserver(queueApply);
  observer.observe(document.body, { childList: true, subtree: true });
  queueApply();
}

load();
