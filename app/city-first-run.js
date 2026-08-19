import { CITY_STORAGE_KEY, loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const CITY_REGISTRY = await loadCityRegistry();
const STORAGE_KEY = CITY_STORAGE_KEY;
const SUPPORTED_CITIES = new Set(CITY_REGISTRY.cities.map((city) => city.id));
const requestedCity = new URLSearchParams(window.location.search).get("city");
const initialPreference = window.__agendaInitialCityPreference ?? null;
const chooserBackdrop = document.querySelector("[data-chooser-backdrop]");
const chooserClose = document.querySelector("[data-chooser-close]");
const chooserTitle = document.querySelector("#chooser-title");
const chooserIntro = document.querySelector("[data-chooser] > p:not(.eyebrow)");
const citySwitch = document.querySelector("[data-city-switch]");
const cityOptions = document.querySelector("[data-city-options]");
const useLocation = document.querySelector("[data-use-location]");

function currentSavedCity() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return SUPPORTED_CITIES.has(saved) ? saved : null;
  } catch {
    return null;
  }
}

const startupCity = SUPPORTED_CITIES.has(requestedCity)
  ? requestedCity
  : SUPPORTED_CITIES.has(initialPreference)
    ? initialPreference
    : currentSavedCity();

function hasExplicitInitialCity() {
  return SUPPORTED_CITIES.has(startupCity);
}

function selectionIsRequired() {
  return chooserBackdrop?.dataset.selectionRequired === "true";
}

function releaseRequiredSelection() {
  if (!chooserBackdrop) return;
  delete chooserBackdrop.dataset.selectionRequired;
}

function setFirstRunCopy() {
  if (chooserTitle) chooserTitle.textContent = "¿Dónde quieres descubrir planes?";
  if (chooserIntro) chooserIntro.textContent = "Elige tu ciudad para adaptar la agenda desde la primera apertura. La recordaremos en este dispositivo.";
}

function openRequiredChooser() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
  if (!chooserBackdrop || !citySwitch) return;
  chooserBackdrop.dataset.selectionRequired = "true";
  citySwitch.click();
  setFirstRunCopy();
  if (chooserClose) chooserClose.hidden = true;
}

async function maybeUsePreviouslyGrantedLocation() {
  openRequiredChooser();
  if (!navigator.permissions?.query || !navigator.geolocation || !useLocation) return;
  try {
    const permission = await navigator.permissions.query({ name: "geolocation" });
    if (permission.state === "granted" && selectionIsRequired()) useLocation.click();
  } catch {
    // The chooser remains available for a manual selection.
  }
}

if (!hasExplicitInitialCity()) maybeUsePreviouslyGrantedLocation();

cityOptions?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-city-option]");
  if (!button) return;
  releaseRequiredSelection();

  const nextCity = String(button.dataset.cityOption || "");
  if (!SUPPORTED_CITIES.has(nextCity) || nextCity === startupCity) return;

  // City-specific presentation modules are chosen once during app startup.
  // Reloading on a real city change prevents Gijon's lightweight runtime from
  // leaking into Valpo/Viña (missing images/old-looking cards), and vice versa.
  event.preventDefault();
  event.stopImmediatePropagation();
  try { localStorage.setItem(STORAGE_KEY, nextCity); } catch {}
  const url = new URL(window.location.href);
  url.searchParams.set("city", nextCity);
  window.location.assign(url.href);
}, { capture: true });

chooserBackdrop?.addEventListener("click", (event) => {
  if (!selectionIsRequired() || event.target !== chooserBackdrop) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, { capture: true });

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || !selectionIsRequired()) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}, { capture: true });

new MutationObserver(() => {
  if (!chooserBackdrop?.hidden) return;
  releaseRequiredSelection();
}).observe(chooserBackdrop, { attributes: true, attributeFilter: ["hidden"] });
