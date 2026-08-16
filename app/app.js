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
  datedSection: document.querySelector("[data-dated-section]"),
  datedTotal: document.querySelector("[data-dated-total]"),
  datedGrid: document.querySelector("[data-dated-grid]"),
  programSection: document.querySelector("[data-program-section]"),
  programTotal: document.querySelector("[data-program-total]"),
  programGrid: document.querySelector("[data-program-grid]"),
  flexibleSection: document.querySelector("[data-flexible-section]"),
  flexibleTotal: document.querySelector("[data-flexible-total]"),
  flexibleGrid: document.querySelector("[data-flexible-grid]"),
  empty: document.querySelector("[data-empty]"),
  emptyCopy: document.querySelector("[data-empty-copy]"),
  searchRow: document.querySelector("[data-search-row]"),
  search: document.querySelector("[data-search]"),
  filters: document.querySelector("[data-filters]"),
  timeFilters: document.querySelectorAll("[data-time-filter]"),
  categoryFilters: document.querySelector("[data-category-filters]"),
};

let activeCity = null;
let allEvents = [];
let activeTimeFilter = "all";
let activeCategory = null;
let categoryCatalog = [];

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

function dateOnlyToDisplayDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return new Date(value);
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12, 0, 0);
}

function formatSchedule(event, city) {
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const end = event?.schedule?.end;
  if (!start) return event?.schedule?.display_text || "Horario por confirmar";

  const formatValue = (value, withWeekday = true) => {
    const date = dateOnlyToDisplayDate(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const hasTime = String(value).includes("T");
    return new Intl.DateTimeFormat(city.locale, {
      timeZone: hasTime ? city.timezone : undefined,
      weekday: withWeekday ? "short" : undefined,
      day: "numeric",
      month: "short",
      hour: hasTime ? "2-digit" : undefined,
      minute: hasTime ? "2-digit" : undefined,
      hour12: false,
    }).format(date);
  };

  try {
    const startDate = String(start).slice(0, 10);
    const endDate = end ? String(end).slice(0, 10) : null;
    if (endDate && endDate !== startDate) return `${formatValue(start)} – ${formatValue(end, false)}`;
    return formatValue(start);
  } catch {
    return event?.schedule?.display_text || String(start);
  }
}

function eventCategory(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
}

function eventCategoryEntries(event) {
  const entries = [];
  const seen = new Set();
  const raw = [event?.primary_category, ...(Array.isArray(event?.categories) ? event.categories : [])];
  for (const category of raw) {
    const label = category?.label;
    if (!label) continue;
    const id = String(category?.id || label).trim().toLocaleLowerCase(activeCity?.locale || "es");
    if (seen.has(id)) continue;
    seen.add(id);
    entries.push({ id, label });
  }
  if (!entries.length) entries.push({ id: "actividad-cultural", label: "Actividad cultural" });
  return entries;
}

function eventLink(event) {
  const candidate = event?.links?.official || event?.links?.source;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function contentGroup(event) {
  if (event?.event_type === "program") return "program";
  if (event?.event_type === "flexible_offer") return "flexible";
  return "dated";
}

function typeBadge(event) {
  if (event?.event_type === "program") return "Programa";
  if (event?.event_type === "flexible_offer") return "Actividad disponible";
  if (event?.event_type === "course") return "Curso / taller";
  return null;
}

function createEventCard(event) {
  const card = document.createElement("article");
  const group = contentGroup(event);
  card.className = `event-card event-card--${group}`;
  const location = [event?.location?.venue, event?.location?.city].filter(Boolean).join(" · ") || "Lugar por confirmar";
  const link = eventLink(event);
  const badge = typeBadge(event);
  card.innerHTML = `
    <div class="card-meta-row">
      <span class="meta">${escapeHtml(eventCategory(event))}</span>
      ${badge ? `<span class="type-badge">${escapeHtml(badge)}</span>` : ""}
    </div>
    <h4>${escapeHtml(event?.title || "Actividad sin título")}</h4>
    <p>${escapeHtml(formatSchedule(event, activeCity))}</p>
    <p>${escapeHtml(location)}</p>
    <div class="event-bottom">
      <span>${event?.price?.is_free === true ? "Gratis" : escapeHtml(event?.price?.display_text || "Precio por confirmar")}</span>
      ${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}
    </div>`;
  return card;
}

function renderGroup(grid, section, total, events) {
  grid.replaceChildren();
  total.textContent = String(events.length);
  section.hidden = events.length === 0;
  for (const event of events) grid.append(createEventCard(event));
}

function renderEvents(events) {
  const groups = { dated: [], program: [], flexible: [] };
  for (const event of events) groups[contentGroup(event)].push(event);

  dom.total.textContent = String(events.length);
  dom.empty.hidden = events.length !== 0;
  renderGroup(dom.datedGrid, dom.datedSection, dom.datedTotal, groups.dated);
  renderGroup(dom.programGrid, dom.programSection, dom.programTotal, groups.program);
  renderGroup(dom.flexibleGrid, dom.flexibleSection, dom.flexibleTotal, groups.flexible);
}

function cityDateKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: activeCity.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function addDays(dateKey, amount) {
  const [year, month, day] = dateKey.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day + amount, 12));
  return date.toISOString().slice(0, 10);
}

function weekdayForDateKey(dateKey) {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day, 12)).getUTCDay();
}

function eventDateRange(event) {
  const schedule = event?.schedule || {};
  const occurrenceStarts = Array.isArray(schedule.occurrences)
    ? schedule.occurrences.map((item) => item?.start).filter(Boolean)
    : [];
  const start = schedule.start || occurrenceStarts[0] || null;
  const end = schedule.end || start;
  return {
    start: start ? String(start).slice(0, 10) : null,
    end: end ? String(end).slice(0, 10) : null,
    occurrences: occurrenceStarts.map((value) => String(value).slice(0, 10)),
  };
}

function eventTouchesDate(event, dateKey) {
  const range = eventDateRange(event);
  if (range.occurrences.includes(dateKey)) return true;
  if (!range.start) return false;
  return range.start <= dateKey && dateKey <= (range.end || range.start);
}

function weekendRange(today) {
  const weekday = weekdayForDateKey(today);
  if (weekday === 6) return { start: today, end: addDays(today, 1) };
  if (weekday === 0) return { start: addDays(today, -1), end: today };
  const daysUntilSaturday = 6 - weekday;
  const start = addDays(today, daysUntilSaturday);
  return { start, end: addDays(start, 1) };
}

function eventMatchesTimeFilter(event) {
  if (activeTimeFilter === "all") return true;
  if (activeTimeFilter === "free") return event?.price?.is_free === true;

  const today = cityDateKey();
  if (activeTimeFilter === "today") return eventTouchesDate(event, today);

  if (activeTimeFilter === "weekend") {
    const weekend = weekendRange(today);
    return eventTouchesDate(event, weekend.start) || eventTouchesDate(event, weekend.end);
  }

  if (activeTimeFilter === "ending") {
    const { end } = eventDateRange(event);
    if (!end) return false;
    return end >= today && end <= addDays(today, 3);
  }

  return true;
}

function eventMatchesSearch(event) {
  const query = dom.search.value.trim().toLocaleLowerCase(activeCity?.locale || "es");
  if (!query) return true;
  const haystack = [
    event?.title,
    eventCategory(event),
    ...eventCategoryEntries(event).map((category) => category.label),
    event?.location?.venue,
    event?.location?.city,
    event?.description,
    typeBadge(event),
  ].filter(Boolean).join(" ").toLocaleLowerCase(activeCity.locale);
  return haystack.includes(query);
}

function eventMatchesCategory(event, categoryId = activeCategory) {
  if (!categoryId) return true;
  return eventCategoryEntries(event).some((category) => category.id === categoryId);
}

function buildCategoryCatalog(events) {
  const categories = new Map();
  for (const event of events) {
    for (const category of eventCategoryEntries(event)) {
      if (!categories.has(category.id)) categories.set(category.id, category.label);
    }
  }
  return [...categories.entries()]
    .map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label, activeCity.locale, { sensitivity: "base" }));
}

function renderCategoryFilters(contextEvents) {
  dom.categoryFilters.replaceChildren();
  const counts = new Map(categoryCatalog.map((category) => [category.id, 0]));
  for (const event of contextEvents) {
    for (const category of eventCategoryEntries(event)) counts.set(category.id, (counts.get(category.id) || 0) + 1);
  }

  for (const category of categoryCatalog) {
    const button = document.createElement("button");
    const count = counts.get(category.id) || 0;
    const active = activeCategory === category.id;
    button.type = "button";
    button.className = `filter-chip category-chip${active ? " is-active" : ""}`;
    button.dataset.categoryFilter = category.id;
    button.setAttribute("aria-pressed", String(active));
    button.innerHTML = `<span>${escapeHtml(category.label)}</span><strong>${count}</strong>`;
    button.addEventListener("click", () => {
      activeCategory = activeCategory === category.id ? null : category.id;
      applyFilters();
    });
    dom.categoryFilters.append(button);
  }
}

function updateTimeFilterButtons() {
  dom.timeFilters.forEach((button) => {
    const active = button.dataset.timeFilter === activeTimeFilter;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function applyFilters() {
  if (!activeCity) return;
  const contextEvents = allEvents.filter((event) => eventMatchesTimeFilter(event) && eventMatchesSearch(event));
  renderCategoryFilters(contextEvents);
  const visibleEvents = contextEvents.filter((event) => eventMatchesCategory(event));
  renderEvents(visibleEvents);
  dom.emptyCopy.textContent = visibleEvents.length
    ? ""
    : `No hay actividades que coincidan con los filtros actuales en ${activeCity.label}.`;
}

function resetFilters() {
  activeTimeFilter = "all";
  activeCategory = null;
  dom.search.value = "";
  updateTimeFilterButtons();
}

async function loadCity(id) {
  const city = CITIES[id];
  if (!city) return;
  activeCity = city;
  saveCity(id);
  hideChooser();
  resetFilters();

  document.body.dataset.city = id;
  document.documentElement.lang = id === "gijon" ? "es-ES" : "es-CL";
  document.title = `Agenda Cultural · ${city.label}`;
  dom.citySwitchLabel.textContent = "Cambiar ciudad";
  dom.citySubtitle.textContent = city.subtitle;
  dom.heroTitle.textContent = `Descubre qué hacer en ${city.label}`;
  dom.heroCopy.textContent = id === "gijon"
    ? "Cultura junto al Cantábrico: agenda local de Gijón/Xixón con horarios adaptados a Asturias."
    : "Cultura entre el mar y los cerros: agenda local de Valparaíso y Viña del Mar.";
  dom.agendaTitle.textContent = city.label;
  dom.searchRow.hidden = false;
  dom.filters.hidden = true;
  setStatus("Cargando agenda", `Estamos buscando las actividades disponibles en ${city.label}.`);

  try {
    const response = await fetch(city.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const dataset = await response.json();
    if (!Array.isArray(dataset.events)) throw new Error("Dataset inválido");
    allEvents = dataset.events;
    categoryCatalog = buildCategoryCatalog(allEvents);
    dom.agenda.hidden = false;
    dom.filters.hidden = false;
    dom.status.hidden = true;
    dom.emptyCopy.textContent = `Todavía no hay actividades publicadas para ${city.label}.`;
    applyFilters();
  } catch (error) {
    allEvents = [];
    categoryCatalog = [];
    dom.agenda.hidden = false;
    dom.filters.hidden = true;
    renderEvents([]);
    setStatus("No pudimos cargar la agenda", `La aplicación no pudo leer el dataset de ${city.label}. Intenta nuevamente más tarde.`);
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
dom.search.addEventListener("input", applyFilters);
dom.timeFilters.forEach((button) => button.addEventListener("click", () => {
  activeTimeFilter = button.dataset.timeFilter;
  updateTimeFilterButtons();
  applyFilters();
}));
dom.chooserBackdrop.addEventListener("click", (event) => { if (event.target === dom.chooserBackdrop && activeCity) hideChooser(); });

document.addEventListener("keydown", (event) => { if (event.key === "Escape" && activeCity) hideChooser(); });

const urlCity = new URLSearchParams(window.location.search).get("city");
const initialCity = CITIES[urlCity] ? urlCity : readSavedCity();
if (initialCity) loadCity(initialCity);
else showChooser(true);