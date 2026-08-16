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

const SECTION_META = Object.freeze({
  hoy: { label: "Hoy", empty: "No hay actividades con fecha para hoy." },
  "fin-de-semana": { label: "Este fin de semana", empty: "No hay actividades fechadas para este fin de semana." },
  proximos: { label: "Próximamente", empty: "No hay próximas actividades fechadas." },
  "terminan-pronto": { label: "Terminan pronto", empty: "No hay actividades en curso que terminen en los próximos días." },
  gratis: { label: "Gratis", empty: "No hay actividades gratuitas con los filtros actuales." },
  "talleres-cursos": { label: "Talleres y cursos", empty: "No hay talleres o cursos con los filtros actuales." },
  todos: { label: "Todas las actividades", empty: "No hay actividades con los filtros actuales." },
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
  discovery: document.querySelector("[data-discovery]"),
  sectionFilters: document.querySelector("[data-section-filters]"),
  sectionButtons: document.querySelectorAll("[data-section-filter]"),
  categoryFilters: document.querySelector("[data-category-filters]"),
  agenda: document.querySelector("[data-agenda]"),
  agendaKicker: document.querySelector("[data-agenda-kicker]"),
  agendaTitle: document.querySelector("[data-agenda-title]"),
  filterSummary: document.querySelector("[data-filter-summary]"),
  filterClear: document.querySelector("[data-filter-clear]"),
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
  sourcesSection: document.querySelector("[data-sources-section]"),
  sourcesTotal: document.querySelector("[data-sources-total]"),
  sourcesGrid: document.querySelector("[data-sources-grid]"),
  empty: document.querySelector("[data-empty]"),
  emptyCopy: document.querySelector("[data-empty-copy]"),
  searchRow: document.querySelector("[data-search-row]"),
  search: document.querySelector("[data-search]"),
};

let activeCity = null;
let allEvents = [];
let activeSection = "proximos";
let activeCategory = "";

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
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const end = event?.schedule?.end;
  if (!start) return event?.schedule?.display_text || "Horario por confirmar";

  const formatValue = (value, withWeekday = true) => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
      const [year, month, day] = String(value).split("-").map(Number);
      const date = new Date(Date.UTC(year, month - 1, day, 12));
      return new Intl.DateTimeFormat(city.locale, {
        timeZone: "UTC",
        weekday: withWeekday ? "short" : undefined,
        day: "numeric",
        month: "short",
      }).format(date);
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(city.locale, {
      timeZone: city.timezone,
      weekday: withWeekday ? "short" : undefined,
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  };

  try {
    const startDate = dateKeyForValue(start, city);
    const endDate = end ? dateKeyForValue(end, city) : null;
    if (endDate && endDate !== startDate) return `${formatValue(start)} – ${formatValue(end, false)}`;
    return formatValue(start);
  } catch {
    return event?.schedule?.display_text || String(start);
  }
}

function eventCategory(event) {
  return event?.primary_category?.label || event?.categories?.[0]?.label || "Actividad cultural";
}

function eventCategoryId(event) {
  return event?.primary_category?.id || event?.categories?.[0]?.id || slugify(eventCategory(event));
}

function eventCategories(event) {
  const values = [];
  if (event?.primary_category?.id || event?.primary_category?.label) values.push(event.primary_category);
  for (const category of event?.categories || []) values.push(category);
  const unique = new Map();
  for (const category of values) {
    const label = String(category?.label || "").trim();
    const id = String(category?.id || slugify(label)).trim();
    if (label && id && !unique.has(id)) unique.set(id, label);
  }
  return unique;
}

function slugify(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "cultura";
}

function eventLink(event) {
  const candidate = event?.links?.official || event?.links?.source;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function eventSourceName(event) {
  return String(event?.source_name || event?.organizer || "").trim();
}

function eventSourceUrl(event) {
  const candidate = event?.source_url || event?.links?.source || event?.links?.official;
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
  if (event?.event_type === "workshop") return "Taller";
  return null;
}

function createEventCard(event) {
  const card = document.createElement("article");
  const group = contentGroup(event);
  card.className = `event-card event-card--${group}`;
  card.dataset.eventId = event?.id || "";
  card.dataset.category = eventCategoryId(event);
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

function dateKeyForDate(date, city) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: city.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function dateKeyForValue(value, city) {
  const text = String(value || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : dateKeyForDate(date, city);
}

function addDays(dateKey, days) {
  const date = new Date(`${dateKey}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function weekdayForKey(dateKey) {
  return new Date(`${dateKey}T12:00:00Z`).getUTCDay();
}

function weekendBounds(todayKey) {
  const weekday = weekdayForKey(todayKey);
  const daysToSaturday = weekday === 6 ? 0 : weekday === 0 ? -1 : 6 - weekday;
  const saturday = addDays(todayKey, daysToSaturday);
  return { start: saturday, end: addDays(saturday, 1) };
}

function scheduleWindows(event) {
  if (["program", "flexible_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.length) {
    return occurrences.map((occurrence) => ({ start: occurrence?.start, end: occurrence?.end || occurrence?.start }));
  }
  if (event?.schedule?.start) return [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }];
  return [];
}

function eventDateRanges(event) {
  return scheduleWindows(event)
    .map((window) => ({
      start: dateKeyForValue(window.start, activeCity),
      end: dateKeyForValue(window.end, activeCity),
    }))
    .filter((range) => range.start && range.end);
}

function rangesOverlap(range, start, end) {
  return range.start <= end && range.end >= start;
}

function isWorkshop(event) {
  if (["course", "workshop"].includes(event?.event_type)) return true;
  const text = [...eventCategories(event).entries()]
    .flat()
    .join(" ")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
  return /taller|curso|formacion/.test(text);
}

function eventMatchesSection(event, sectionId) {
  if (sectionId === "todos") return true;
  if (sectionId === "gratis") return event?.price?.is_free === true;
  if (sectionId === "talleres-cursos") return isWorkshop(event);

  const today = dateKeyForDate(new Date(), activeCity);
  const ranges = eventDateRanges(event);
  if (!ranges.length) return false;

  if (sectionId === "hoy") return ranges.some((range) => rangesOverlap(range, today, today));
  if (sectionId === "fin-de-semana") {
    const weekend = weekendBounds(today);
    return ranges.some((range) => rangesOverlap(range, weekend.start, weekend.end));
  }
  if (sectionId === "terminan-pronto") {
    const limit = addDays(today, 3);
    return ranges.some((range) => range.start <= today && range.end > today && range.end <= limit);
  }
  if (sectionId === "proximos") return ranges.some((range) => range.end >= today);
  return true;
}

function eventMatchesCategory(event, categoryId) {
  if (!categoryId) return true;
  return eventCategories(event).has(categoryId) || eventCategoryId(event) === categoryId;
}

function eventSortKey(event) {
  const windows = scheduleWindows(event);
  const candidate = windows[0]?.start || event?.schedule?.start;
  if (!candidate) return Number.POSITIVE_INFINITY;
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(candidate))) return Date.parse(`${candidate}T12:00:00Z`);
  const value = Date.parse(candidate);
  return Number.isFinite(value) ? value : Number.POSITIVE_INFINITY;
}

function sortEvents(events) {
  return [...events].sort((a, b) => {
    const aGroup = contentGroup(a) === "dated" ? 0 : contentGroup(a) === "program" ? 1 : 2;
    const bGroup = contentGroup(b) === "dated" ? 0 : contentGroup(b) === "program" ? 1 : 2;
    if (aGroup !== bGroup) return aGroup - bGroup;
    const dateDiff = eventSortKey(a) - eventSortKey(b);
    if (Number.isFinite(dateDiff) && dateDiff !== 0) return dateDiff;
    return String(a?.title || "").localeCompare(String(b?.title || ""), activeCity?.locale || "es");
  });
}

function renderGroup(grid, section, total, events) {
  grid.replaceChildren();
  total.textContent = String(events.length);
  section.hidden = events.length === 0;
  for (const event of events) grid.append(createEventCard(event));
}

function collectCategoryCounts(events) {
  const categories = new Map();
  for (const event of events) {
    for (const [id, label] of eventCategories(event)) {
      const current = categories.get(id) || { id, label, count: 0 };
      current.count += 1;
      categories.set(id, current);
    }
  }
  return [...categories.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, activeCity?.locale || "es"));
}

function collectSources(events) {
  const sources = new Map();
  for (const event of events) {
    const name = eventSourceName(event);
    if (!name) continue;
    const key = name.toLocaleLowerCase(activeCity?.locale || "es");
    const current = sources.get(key) || { name, url: null, count: 0, official: false };
    current.count += 1;
    current.official ||= event?.public_status?.source_official === true;
    current.url ||= eventSourceUrl(event);
    sources.set(key, current);
  }
  return [...sources.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, activeCity?.locale || "es"));
}

function renderSources() {
  const sources = collectSources(allEvents);
  dom.sourcesGrid.replaceChildren();
  dom.sourcesTotal.textContent = String(sources.length);
  dom.sourcesSection.hidden = sources.length === 0;

  for (const source of sources) {
    const card = document.createElement("article");
    card.className = "source-card";
    const heading = document.createElement("div");
    heading.className = "source-card-heading";
    const name = document.createElement("strong");
    name.textContent = source.name;
    heading.append(name);
    if (source.official) {
      const badge = document.createElement("span");
      badge.className = "source-official-badge";
      badge.textContent = "Oficial";
      heading.append(badge);
    }
    card.append(heading);

    const count = document.createElement("small");
    count.textContent = `${source.count} ${source.count === 1 ? "actividad" : "actividades"} en esta agenda`;
    card.append(count);

    if (source.url) {
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Abrir referencia →";
      card.append(link);
    }
    dom.sourcesGrid.append(card);
  }
}

function renderCategories() {
  const categories = collectCategoryCounts(allEvents);
  dom.categoryFilters.replaceChildren();

  const allButton = document.createElement("button");
  allButton.type = "button";
  allButton.dataset.categoryFilter = "";
  allButton.className = `category-chip${activeCategory === "" ? " active" : ""}`;
  allButton.setAttribute("aria-pressed", activeCategory === "" ? "true" : "false");
  allButton.innerHTML = `<span>Todas</span><small>${allEvents.length}</small>`;
  dom.categoryFilters.append(allButton);

  for (const category of categories) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.categoryFilter = category.id;
    button.className = `category-chip${activeCategory === category.id ? " active" : ""}`;
    button.setAttribute("aria-pressed", activeCategory === category.id ? "true" : "false");
    button.innerHTML = `<span>${escapeHtml(category.label)}</span><small>${category.count}</small>`;
    dom.categoryFilters.append(button);
  }
}

function updateSectionCounts() {
  for (const button of dom.sectionButtons) {
    const section = button.dataset.sectionFilter;
    const count = allEvents.filter((event) => eventMatchesSection(event, section)).length;
    const countNode = button.querySelector("[data-section-count]");
    if (countNode) countNode.textContent = String(count);
    const active = section === activeSection;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

function currentFilteredEvents() {
  const query = dom.search.value.trim().toLocaleLowerCase(activeCity?.locale || "es");
  return sortEvents(allEvents.filter((event) => {
    if (!eventMatchesSection(event, activeSection)) return false;
    if (!eventMatchesCategory(event, activeCategory)) return false;
    if (!query) return true;
    const haystack = [
      event?.title,
      ...eventCategories(event).values(),
      event?.location?.venue,
      event?.location?.city,
      event?.description,
      eventSourceName(event),
      event?.organizer,
      typeBadge(event),
    ].filter(Boolean).join(" ").toLocaleLowerCase(activeCity.locale);
    return haystack.includes(query);
  }));
}

function updateResultHeading(events) {
  const meta = SECTION_META[activeSection] || SECTION_META.todos;
  dom.agendaKicker.textContent = activeSection === "hoy" ? "Qué hacer hoy" : "Agenda actual";
  dom.agendaTitle.textContent = meta.label;
  dom.total.textContent = String(events.length);

  const parts = [`${events.length} ${events.length === 1 ? "actividad" : "actividades"}`];
  if (activeCategory) {
    const category = collectCategoryCounts(allEvents).find((item) => item.id === activeCategory);
    if (category) parts.push(category.label);
  }
  if (dom.search.value.trim()) parts.push(`“${dom.search.value.trim()}”`);
  dom.filterSummary.textContent = parts.join(" · ");
  dom.filterClear.hidden = activeCategory === "" && !dom.search.value.trim() && activeSection === defaultSection();
  dom.emptyCopy.textContent = meta.empty;
}

function renderEvents() {
  const events = currentFilteredEvents();
  const groups = { dated: [], program: [], flexible: [] };
  for (const event of events) groups[contentGroup(event)].push(event);

  dom.empty.hidden = events.length !== 0;
  renderGroup(dom.datedGrid, dom.datedSection, dom.datedTotal, groups.dated);
  renderGroup(dom.programGrid, dom.programSection, dom.programTotal, groups.program);
  renderGroup(dom.flexibleGrid, dom.flexibleSection, dom.flexibleTotal, groups.flexible);
  updateResultHeading(events);
  updateSectionCounts();
  renderCategories();
  renderSources();
}

function defaultSection() {
  return allEvents.some((event) => eventMatchesSection(event, "hoy")) ? "hoy" : "proximos";
}

function resetDiscoveryFilters() {
  activeSection = defaultSection();
  activeCategory = "";
  dom.search.value = "";
  renderEvents();
}

async function loadCity(id) {
  const city = CITIES[id];
  if (!city) return;
  activeCity = city;
  saveCity(id);
  hideChooser();

  document.documentElement.lang = id === "gijon" ? "es-ES" : "es-CL";
  document.documentElement.dataset.city = id;
  document.title = `Agenda Cultural · ${city.label}`;
  dom.citySwitchLabel.textContent = city.label;
  dom.citySubtitle.textContent = city.subtitle;
  dom.heroTitle.textContent = `Descubre qué hacer en ${city.label}`;
  dom.heroCopy.textContent = `Agenda local de ${city.label}: explora qué hay hoy, este fin de semana o por categoría.`;
  dom.searchRow.hidden = false;
  dom.search.value = "";
  dom.discovery.hidden = true;
  dom.agenda.hidden = true;
  setStatus("Cargando agenda", `Estamos buscando las actividades disponibles en ${city.label}.`);

  try {
    const response = await fetch(city.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const dataset = await response.json();
    if (!Array.isArray(dataset.events)) throw new Error("Dataset inválido");
    allEvents = dataset.events;
    activeCategory = "";
    activeSection = defaultSection();
    dom.discovery.hidden = false;
    dom.agenda.hidden = false;
    dom.status.hidden = true;
    renderEvents();
  } catch (error) {
    allEvents = [];
    activeCategory = "";
    activeSection = "todos";
    dom.discovery.hidden = true;
    dom.agenda.hidden = false;
    renderEvents();
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
dom.search.addEventListener("input", renderEvents);
dom.filterClear.addEventListener("click", resetDiscoveryFilters);
dom.sectionFilters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-section-filter]");
  if (!button) return;
  activeSection = button.dataset.sectionFilter;
  renderEvents();
  dom.agenda.scrollIntoView({ behavior: "smooth", block: "start" });
});
dom.categoryFilters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category-filter]");
  if (!button) return;
  activeCategory = button.dataset.categoryFilter || "";
  renderEvents();
  dom.agenda.scrollIntoView({ behavior: "smooth", block: "start" });
});
dom.chooserBackdrop.addEventListener("click", (event) => { if (event.target === dom.chooserBackdrop && activeCity) hideChooser(); });

document.addEventListener("keydown", (event) => { if (event.key === "Escape" && activeCity) hideChooser(); });

const savedCity = readSavedCity();
if (savedCity) loadCity(savedCity);
else showChooser(true);
