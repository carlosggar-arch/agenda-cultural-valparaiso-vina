const STORAGE_KEY = "agenda-cultural-city";

const CITIES = Object.freeze({
  valparaiso: {
    id: "valparaiso",
    label: "Valparaíso / Viña del Mar",
    subtitle: "Valparaíso / Viña del Mar",
    country: "Chile",
    timezone: "America/Santiago",
    locale: "es-CL",
    dataset: "../agenda_web.json",
    center: { lat: -33.02, lon: -71.55 },
    radiusKm: 55,
  },
  gijon: {
    id: "gijon",
    label: "Gijón / Xixón",
    subtitle: "Gijón / Xixón",
    country: "España",
    timezone: "Europe/Madrid",
    locale: "es-ES",
    dataset: "./data/gijon/agenda_web.json",
    center: { lat: 43.5322, lon: -5.6611 },
    radiusKm: 45,
  },
});

const dom = {
  chooserBackdrop: document.querySelector("[data-chooser-backdrop]"),
  chooserClose: document.querySelector("[data-chooser-close]"),
  chooserMessage: document.querySelector("[data-chooser-message]"),
  cityOptions: document.querySelectorAll("[data-city-option]"),
  useLocation: document.querySelector("[data-use-location]"),
  citySwitch: document.querySelector("[data-city-switch]"),
  citySwitchLabel: document.querySelector("[data-city-switch-label]"),
  citySubtitle: document.querySelector("[data-city-subtitle]"),
  heroTitle: document.querySelector("[data-hero-title]"),
  heroCopy: document.querySelector("[data-hero-copy]"),
  status: document.querySelector("[data-status]"),
  agenda: document.querySelector("[data-agenda]"),
  agendaTitle: document.querySelector("[data-agenda-title]"),
  total: document.querySelector("[data-total]"),
  grid: document.querySelector("[data-event-grid]"),
  empty: document.querySelector("[data-empty]"),
  emptyCopy: document.querySelector("[data-empty-copy]"),
  searchRow: document.querySelector("[data-search-row]"),
  search: document.querySelector("[data-search]"),
};

let activeCity = null;
let allEvents = [];

function showChooser(force = false) {
  dom.chooserBackdrop.hidden = false;
  dom.chooserClose.hidden = force;
  dom.chooserMessage.textContent = "";
}

function hideChooser() {
  dom.chooserBackdrop.hidden = true;
}

function setStatus(title, copy) {
  dom.status.hidden = false;
  dom.status.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(copy)}</p>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function readSavedCity() {
  try {
    const id = localStorage.getItem(STORAGE_KEY);
    return CITIES[id] ? id : null;
  } catch {
    return null;
  }
}

function saveCity(id) {
  try { localStorage.setItem(STORAGE_KEY, id); } catch {}
}

function formatSchedule(event, city) {
  const value = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  if (!value) return event?.schedule?.display_text || "Horario por confirmar";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return event?.schedule?.display_text || String(value);
  try {
    return new Intl.DateTimeFormat(city.locale, {
      timeZone: city.timezone,
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: String(value).includes("T") ? "2-digit" : undefined,
      minute: String(value).includes("T") ? "2-digit" : undefined,
      hour12: false,
    }).format(date);
  } catch {
    return event?.schedule?.display_text || String(value);
  }
}

function eventCategory(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
}

function eventLink(event) {
  const candidate = event?.links?.official || event?.links?.source;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function renderEvents(events) {
  dom.grid.replaceChildren();
  dom.total.textContent = String(events.length);
  dom.empty.hidden = events.length !== 0;

  for (const event of events) {
    const card = document.createElement("article");
    card.className = "event-card";
    const location = [event?.location?.venue, event?.location?.city].filter(Boolean).join(" · ") || "Lugar por confirmar";
    const link = eventLink(event);
    card.innerHTML = `
      <span class="meta">${escapeHtml(eventCategory(event))}</span>
      <h3>${escapeHtml(event?.title || "Actividad sin título")}</h3>
      <p>${escapeHtml(formatSchedule(event, activeCity))}</p>
      <p>${escapeHtml(location)}</p>
      <div class="event-bottom">
        <span>${event?.price?.is_free === true ? "Gratis" : escapeHtml(event?.price?.display_text || "Precio por confirmar")}</span>
        ${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}
      </div>`;
    dom.grid.append(card);
  }
}

function filterEvents() {
  const query = dom.search.value.trim().toLocaleLowerCase(activeCity?.locale || "es");
  if (!query) return renderEvents(allEvents);
  renderEvents(allEvents.filter((event) => {
    const haystack = [
      event?.title,
      eventCategory(event),
      event?.location?.venue,
      event?.location?.city,
      event?.description,
    ].filter(Boolean).join(" ").toLocaleLowerCase(activeCity.locale);
    return haystack.includes(query);
  }));
}

async function loadCity(id) {
  const city = CITIES[id];
  if (!city) return;
  activeCity = city;
  saveCity(id);
  hideChooser();

  document.documentElement.lang = id === "gijon" ? "es-ES" : "es-CL";
  document.title = `Agenda Cultural · ${city.label}`;
  dom.citySwitchLabel.textContent = city.label;
  dom.citySubtitle.textContent = city.subtitle;
  dom.heroTitle.textContent = `Descubre qué hacer en ${city.label}`;
  dom.heroCopy.textContent = `La aplicación carga únicamente las actividades de ${city.label}. Puedes cambiar de ciudad cuando quieras.`;
  dom.agendaTitle.textContent = city.label;
  dom.searchRow.hidden = false;
  dom.search.value = "";
  setStatus("Cargando agenda", `Estamos buscando las actividades disponibles en ${city.label}.`);

  try {
    const response = await fetch(city.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const dataset = await response.json();
    if (!Array.isArray(dataset.events)) throw new Error("Dataset inválido");
    allEvents = dataset.events;
    dom.agenda.hidden = false;
    dom.status.hidden = true;
    dom.emptyCopy.textContent = `Todavía no hay eventos publicados para ${city.label}.`;
    renderEvents(allEvents);
  } catch (error) {
    allEvents = [];
    dom.agenda.hidden = false;
    renderEvents([]);
    if (id === "gijon") {
      setStatus("Gijón está preparado", "La instancia de Gijón ya existe en la aplicación, pero su dataset público todavía no ha sido conectado. Valparaíso / Viña sigue funcionando de forma independiente.");
    } else {
      setStatus("No pudimos cargar la agenda", "La aplicación no pudo leer el dataset público de Valparaíso / Viña. Intenta nuevamente más tarde.");
    }
  }
}

function haversineKm(a, b) {
  const R = 6371;
  const toRad = (x) => x * Math.PI / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

function suggestCityFromCoordinates(lat, lon) {
  const point = { lat, lon };
  const ranked = Object.values(CITIES)
    .map((city) => ({ city, distance: haversineKm(point, city.center) }))
    .sort((a, b) => a.distance - b.distance);
  const nearest = ranked[0];
  return nearest && nearest.distance <= nearest.city.radiusKm ? nearest.city.id : null;
}

function useLocation() {
  dom.chooserMessage.textContent = "";
  if (!navigator.geolocation) {
    dom.chooserMessage.textContent = "Este dispositivo no ofrece geolocalización. Elige una ciudad manualmente.";
    return;
  }
  dom.useLocation.disabled = true;
  dom.useLocation.textContent = "Buscando tu ubicación…";
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      dom.useLocation.disabled = false;
      dom.useLocation.innerHTML = '<span aria-hidden="true">◎</span> Usar mi ubicación';
      const id = suggestCityFromCoordinates(coords.latitude, coords.longitude);
      if (id) loadCity(id);
      else dom.chooserMessage.textContent = "No estás cerca de ninguna de las agendas disponibles. Elige una ciudad manualmente.";
    },
    () => {
      dom.useLocation.disabled = false;
      dom.useLocation.innerHTML = '<span aria-hidden="true">◎</span> Usar mi ubicación';
      dom.chooserMessage.textContent = "No pudimos acceder a tu ubicación. Elige una ciudad manualmente.";
    },
    { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 },
  );
}

dom.cityOptions.forEach((button) => button.addEventListener("click", () => loadCity(button.dataset.cityOption)));
dom.citySwitch.addEventListener("click", () => showChooser(false));
dom.chooserClose.addEventListener("click", hideChooser);
dom.useLocation.addEventListener("click", useLocation);
dom.search.addEventListener("input", filterEvents);
dom.chooserBackdrop.addEventListener("click", (event) => { if (event.target === dom.chooserBackdrop && activeCity) hideChooser(); });

document.addEventListener("keydown", (event) => { if (event.key === "Escape" && activeCity) hideChooser(); });

const savedCity = readSavedCity();
if (savedCity) loadCity(savedCity);
else showChooser(true);
