const STORAGE_KEY = "agenda-cultural-city";
const SUPPORTED_CITIES = new Set(["valparaiso", "gijon"]);
const requestedCity = new URLSearchParams(window.location.search).get("city");
const initialPreference = window.__agendaInitialCityPreference ?? null;
const chooserBackdrop = document.querySelector("[data-chooser-backdrop]");
const chooserClose = document.querySelector("[data-chooser-close]");
const citySwitch = document.querySelector("[data-city-switch]");
const cityOptions = document.querySelectorAll("[data-city-option]");
const useLocation = document.querySelector("[data-use-location]");

function currentSavedCity() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return SUPPORTED_CITIES.has(saved) ? saved : null;
  } catch {
    return null;
  }
}

function hasExplicitInitialCity() {
  return SUPPORTED_CITIES.has(requestedCity)
    || SUPPORTED_CITIES.has(initialPreference)
    || Boolean(currentSavedCity());
}

function selectionIsRequired() {
  return chooserBackdrop?.dataset.selectionRequired === "true";
}

function releaseRequiredSelection() {
  if (!chooserBackdrop) return;
  delete chooserBackdrop.dataset.selectionRequired;
}

function openRequiredChooser() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
  if (!chooserBackdrop || !citySwitch) return;
  chooserBackdrop.dataset.selectionRequired = "true";
  citySwitch.click();
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

cityOptions.forEach((button) => button.addEventListener("click", releaseRequiredSelection, { once: true }));

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
