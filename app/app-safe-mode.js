const STORAGE_KEY = "agenda-cultural-city";

function safeCityId(value) {
  const id = String(value || "").trim().toLowerCase();
  return /^[a-z0-9][a-z0-9-]{0,63}$/.test(id) ? id : "";
}

function text(value, fallback = "") {
  return String(value ?? "").trim() || fallback;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function selectedCityId(registry) {
  const query = safeCityId(new URLSearchParams(location.search).get("city"));
  const documentCity = safeCityId(document.documentElement.dataset.city);
  let saved = "";
  try { saved = safeCityId(localStorage.getItem(STORAGE_KEY)); } catch {}
  const candidates = [query, documentCity, saved, safeCityId(registry?.default_city)];
  return candidates.find((id) => registry?.cities?.some((city) => city?.id === id)) || registry?.cities?.[0]?.id || "";
}

function dateKey(value) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/);
  return match?.[1] || "";
}

function scheduleText(event, city) {
  const schedule = event?.schedule || {};
  const start = schedule.start || schedule.occurrences?.[0]?.start;
  const end = schedule.end;
  if (!start) return text(schedule.display_text, "Horario por confirmar");
  try {
    const formatter = new Intl.DateTimeFormat(city?.locale || "es-CL", {
      timeZone: city?.timezone || "America/Santiago",
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: /T\d{2}:\d{2}/.test(String(start)) ? "2-digit" : undefined,
      minute: /T\d{2}:\d{2}/.test(String(start)) ? "2-digit" : undefined,
      hour12: false,
    });
    if (dateKey(start) && dateKey(end) && dateKey(start) !== dateKey(end)) {
      return `${formatter.format(new Date(start))} – ${dateKey(end)}`;
    }
    return formatter.format(new Date(start));
  } catch {
    return text(schedule.display_text, text(start, "Horario por confirmar"));
  }
}

function futureEvents(events, city) {
  const now = new Date();
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: city?.timezone || "America/Santiago",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
  const publicEvents = (Array.isArray(events) ? events : []).filter((event) => event?.event_type !== "program");
  const upcoming = publicEvents.filter((event) => {
    const schedule = event?.schedule || {};
    const end = dateKey(schedule.end) || dateKey(schedule.start) || dateKey(schedule.occurrences?.at?.(-1)?.end) || dateKey(schedule.occurrences?.at?.(-1)?.start);
    return !end || end >= today;
  });
  return (upcoming.length ? upcoming : publicEvents).slice(0, 40);
}

function renderCard(event, city) {
  const article = document.createElement("article");
  article.className = "event-card event-card--dated";
  article.dataset.eventId = text(event?.id);
  const category = text(event?.primary_category?.label || event?.categories?.[0]?.label, "Actividad cultural");
  const venue = [event?.location?.venue, event?.location?.city].filter(Boolean).join(" · ") || "Lugar por confirmar";
  const price = event?.price?.is_free === true ? "Gratis" : text(event?.price?.display_text, "Consultar precio");
  const link = event?.links?.official || event?.links?.source || event?.source_url;
  article.innerHTML = `
    <div class="card-meta-row"><span class="meta">${escapeHtml(category)}</span><span class="type-badge">Modo seguro</span></div>
    <h4>${escapeHtml(text(event?.title, "Actividad cultural"))}</h4>
    <p>${escapeHtml(scheduleText(event, city))}</p>
    <p>${escapeHtml(venue)}</p>
    <div class="event-bottom"><span>${escapeHtml(price)}</span>${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}</div>`;
  return article;
}

function renderSafeAgenda(city, dataset) {
  const events = futureEvents(dataset?.events, city);
  const grid = document.querySelector("[data-dated-grid]");
  const section = document.querySelector("[data-dated-section]");
  const agenda = document.querySelector("[data-agenda]");
  const discovery = document.querySelector("[data-discovery]");
  const status = document.querySelector("[data-status]");
  if (!(grid && section && agenda)) throw new Error("Shell de agenda incompleto");

  grid.replaceChildren(...events.map((event) => renderCard(event, city)));
  const datedTotal = document.querySelector("[data-dated-total]");
  const total = document.querySelector("[data-total]");
  if (datedTotal) datedTotal.textContent = String(events.length);
  if (total) total.textContent = String(events.length);
  const title = document.querySelector("[data-agenda-title]");
  const kicker = document.querySelector("[data-agenda-kicker]");
  const summary = document.querySelector("[data-filter-summary]");
  if (title) title.textContent = "Agenda disponible";
  if (kicker) kicker.textContent = "Modo seguro";
  if (summary) summary.textContent = "La agenda básica está activa; las mejoras opcionales se han omitido temporalmente.";

  document.querySelector("[data-program-section]")?.setAttribute("hidden", "");
  document.querySelector("[data-flexible-section]")?.setAttribute("hidden", "");
  document.querySelector("[data-sources-section]")?.setAttribute("hidden", "");
  section.hidden = events.length === 0;
  agenda.hidden = false;
  if (discovery) discovery.hidden = true;
  if (status) status.hidden = true;

  document.documentElement.lang = city?.lang || city?.locale || "es";
  document.documentElement.dataset.city = city.id;
  const cityLabel = text(city?.label, "Agenda local");
  const switchLabel = document.querySelector("[data-city-switch-label]");
  const subtitle = document.querySelector("[data-city-subtitle]");
  const headerTitle = document.querySelector("[data-header-city-title]");
  if (switchLabel) switchLabel.textContent = cityLabel;
  if (subtitle) subtitle.textContent = cityLabel;
  if (headerTitle) headerTitle.textContent = cityLabel;

  document.documentElement.dataset.vivamosSafeMode = "active";
  document.documentElement.dataset.vivamosReady = "true";
  window.dispatchEvent(new CustomEvent("vivamos:core-ready", { detail: { city: city.id, mode: "safe" } }));
}

export async function startSafeMode() {
  if (document.documentElement.dataset.vivamosReady === "true") return;
  const registryResponse = await fetch("./cities.json", { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!registryResponse.ok) throw new Error(`Registro de ciudades HTTP ${registryResponse.status}`);
  const registry = await registryResponse.json();
  const cityId = selectedCityId(registry);
  const city = (registry?.cities || []).find((candidate) => candidate?.id === cityId);
  if (!city?.dataset) throw new Error("No hay ciudad válida para el modo seguro");

  const datasetResponse = await fetch(city.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
  if (!datasetResponse.ok) throw new Error(`Dataset HTTP ${datasetResponse.status}`);
  const dataset = await datasetResponse.json();
  if (!Array.isArray(dataset?.events)) throw new Error("Dataset inválido en modo seguro");
  if (document.documentElement.dataset.vivamosReady === "true") return;
  renderSafeAgenda(city, dataset);
}
