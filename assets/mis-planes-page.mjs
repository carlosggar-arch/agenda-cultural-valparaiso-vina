import { FAVORITES_CHANGED_EVENT, FAVORITES_STORAGE_KEY } from "./favorites-core.mjs?v=20260817";
import { buildMyPlansSection, installFavoritesStyles } from "./favorites-view.mjs?v=20260817";

const CITY_CONFIG = Object.freeze({
  valparaiso: { locale: "es-CL", title: "Valparaíso / Viña del Mar", datasetWeb: "../agenda_web.json", datasetApp: "../agenda_web.json" },
  gijon: { locale: "es-ES", title: "Gijón / Xixón", datasetWeb: null, datasetApp: "./data/gijon/agenda_web.json" },
});

function currentCity() {
  const explicit = String(document.body.dataset.favoritesCity || "").trim();
  if (CITY_CONFIG[explicit]) return explicit;
  const requested = new URL(window.location.href).searchParams.get("city");
  if (CITY_CONFIG[requested]) return requested;
  try {
    const saved = localStorage.getItem("agenda-cultural-city");
    if (CITY_CONFIG[saved]) return saved;
  } catch {}
  return "valparaiso";
}

function mode() {
  return document.body.dataset.favoritesMode === "app" ? "app" : "web";
}

function eventPageHref(city, event) {
  const id = String(event?.id || "").trim();
  return id ? new URL(`../evento/${city}/${encodeURIComponent(id)}/`, window.location.href).href : null;
}

function datasetUrl(city) {
  const config = CITY_CONFIG[city];
  return mode() === "app" ? config.datasetApp : config.datasetWeb;
}

function backHref(city) {
  return mode() === "app" ? `./?city=${encodeURIComponent(city)}` : "../";
}

function updateChrome(city) {
  const config = CITY_CONFIG[city];
  document.documentElement.dataset.city = city;
  const place = document.querySelector("[data-my-plans-place]");
  if (place) place.textContent = config.title;
  for (const back of document.querySelectorAll("[data-my-plans-back]")) back.href = backHref(city);
  document.title = `Mis planes · ${config.title}`;
}

async function loadEventMap(city) {
  const url = datasetUrl(city);
  if (!url) return new Map();
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return new Map();
    const payload = await response.json();
    return new Map((payload?.events || []).map((event) => [String(event.id), event]));
  } catch {
    return new Map();
  }
}

let eventMap = new Map();
const city = currentCity();

function render() {
  const host = document.querySelector("[data-my-plans-page]");
  if (!host) return;
  host.replaceChildren(buildMyPlansSection({
    city,
    locale: CITY_CONFIG[city].locale,
    eventMap,
    eventPageHref: (event) => eventPageHref(city, event),
    onChanged: render,
  }));
}

async function start() {
  installFavoritesStyles("../assets/favorites.css?v=20260817-compact");
  updateChrome(city);
  eventMap = await loadEventMap(city);
  render();
  window.addEventListener(FAVORITES_CHANGED_EVENT, render);
  window.addEventListener("storage", (event) => {
    if (event.key === FAVORITES_STORAGE_KEY) render();
  });
}

start();
