import {
  AGENDA_SECTIONS,
  buildIcs,
  calendarOccurrences,
  clearFilterParams,
  collectCategories,
  collectCities,
  eventTypeLabel,
  eventsForSection,
  fetchChangesDataset,
  fetchDataset,
  filterEvents,
  filtersFromSearchParams,
  filtersToSearchParams,
  findEventById,
  formatGeneratedAt,
  googleCalendarUrl,
  permanentEventUrl,
  priceLabel,
  publicStatusLabels,
  safeHttpUrl,
  scheduleLabel,
  sectionCounts,
  sectionFromLocation,
} from "./agenda-core.mjs";

const elements = {
  status: document.querySelector("#app-status"),
  statusTitle: document.querySelector("#status-title"),
  statusMessage: document.querySelector("#status-message"),
  results: document.querySelector("#agenda-results"),
  grid: document.querySelector("#event-grid"),
  resultCount: document.querySelector("#results-count"),
  publicCount: document.querySelector("#public-count"),
  updated: document.querySelector("#last-updated"),
  dialog: document.querySelector("#event-detail"),
  detailContent: document.querySelector("#detail-content"),
  detailClose: document.querySelector("#detail-close"),
  query: document.querySelector("#filter-query"),
  city: document.querySelector("#filter-city"),
  price: document.querySelector("#filter-price"),
  period: document.querySelector("#filter-period"),
  from: document.querySelector("#filter-from"),
  to: document.querySelector("#filter-to"),
  categories: document.querySelector("#filter-categories"),
  range: document.querySelector("#custom-range"),
  chips: document.querySelector("#active-filters"),
  clear: document.querySelector("#clear-filters"),
  noResults: document.querySelector("#no-results"),
  noResultsClear: document.querySelector("#no-results-clear"),
  changes: document.querySelector("#agenda-changes"),
  changesCount: document.querySelector("#changes-count"),
  changesContent: document.querySelector("#changes-content"),
  sectionLinks: document.querySelector("#section-links"),
  resultsTitle: document.querySelector("#results-title"),
};

function renderChanges(changes) {
  const definitions = [
    ["added", "Nuevos"], ["updated", "Actualizados"],
    ["removed_from_public", "Ya no aparecen en la agenda"], ["cancelled", "Cancelados"],
  ];
  const total = definitions.reduce((sum, [key]) => sum + changes[key].length, 0);
  if (!total) {
    elements.changes.hidden = true;
    return;
  }
  const groups = definitions.flatMap(([key, label]) => {
    if (!changes[key].length) return [];
    const section = element("section", "change-group");
    section.append(element("h3", null, `${label} (${changes[key].length})`));
    const list = element("ul");
    changes[key].slice(0, 8).forEach((item) => {
      const row = element("li");
      const event = findEventById(state.events, item.id);
      if (event) {
        const button = element("button", "text-button", item.title);
        button.type = "button";
        button.addEventListener("click", () => openDetail(item.id, button, true));
        row.append(button);
      } else {
        row.append(document.createTextNode(item.title));
      }
      if (key === "updated") {
        const labels = {
          title: "título", date: "fecha", time: "hora", venue: "lugar",
          city: "ciudad", price: "precio", registration: "inscripción",
          public_status: "estado público",
        };
        row.append(document.createTextNode(
          ` — ${Object.keys(item.changes).map((field) => labels[field] || field).join(", ")}`,
        ));
      }
      list.append(row);
    });
    section.append(list);
    return [section];
  });
  elements.changesContent.replaceChildren(...groups);
  elements.changesCount.textContent = `${total} ${total === 1 ? "novedad" : "novedades"}`;
  elements.changes.hidden = false;
}

const state = {
  events: [],
  categories: [],
  cities: [],
  filters: filtersFromSearchParams(location.search),
  section: sectionFromLocation(location.search, location.hash),
  detailTrigger: null,
  syncingHistory: false,
  publicationDate: null,
};

function setSection(sectionId, updateUrl = true) {
  state.section = sectionId;
  if (updateUrl) {
    const params = new URLSearchParams(location.search);
    params.set("seccion", sectionId);
    const query = params.toString();
    history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}#seccion-${sectionId}`);
  }
  applyFilters(false);
}

function renderSectionNavigation(filteredEvents) {
  const counts = sectionCounts(filteredEvents);
  const links = AGENDA_SECTIONS.map(({ id, label }) => {
    const link = element("a", "section-link", `${label} (${counts[id]})`);
    const params = new URLSearchParams(location.search);
    params.set("seccion", id);
    link.href = `?${params.toString()}#seccion-${id}`;
    link.id = `seccion-${id}`;
    if (id === state.section) {
      link.classList.add("is-active");
      link.setAttribute("aria-current", "page");
    }
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setSection(id, true);
    });
    return link;
  });
  elements.sectionLinks.replaceChildren(...links);
}

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined && text !== null && text !== "") node.textContent = String(text);
  return node;
}

function setStatus(kind, title, message) {
  elements.status.hidden = false;
  elements.status.dataset.state = kind;
  elements.statusTitle.textContent = title;
  elements.statusMessage.textContent = message;
  const mark = elements.status.querySelector(".loading-mark");
  if (mark) mark.hidden = kind !== "loading";
}

function hideStatus() {
  elements.status.hidden = true;
}

function addMeta(list, label, value) {
  if (value === undefined || value === null || value === "") return;
  const row = element("div");
  row.append(element("dt", null, label), element("dd", null, value));
  list.append(row);
}

function externalLink(label, url, className = "button-link button-secondary") {
  const safeUrl = safeHttpUrl(url);
  if (!safeUrl) return null;
  const link = element("a", className, label);
  link.href = safeUrl;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  return link;
}

function appendPublicLinks(container, links = {}) {
  [
    ["Sitio oficial", links.official],
    ["Comprar entradas", links.tickets],
    ["Inscribirse", links.registration],
  ].forEach(([label, url]) => {
    const link = externalLink(label, url);
    if (link) container.append(link);
  });
}

function downloadIcs(event, occurrence, permalink) {
  const content = buildIcs(event, occurrence, permalink);
  if (!content) return;
  const url = URL.createObjectURL(new Blob([content], { type: "text/calendar;charset=utf-8" }));
  const anchor = element("a");
  anchor.href = url;
  anchor.download = `${event.id}-${String(occurrence.start).slice(0, 10)}.ics`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const field = element("textarea");
  field.value = value;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.append(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();
  if (!copied) throw new Error("Clipboard unavailable");
}

function calendarAndShareActions(event) {
  const section = element("section", "calendar-actions");
  section.append(element("h3", null, "Guardar o compartir"));
  const message = element("p", "action-message");
  message.setAttribute("aria-live", "polite");
  const permalink = permanentEventUrl(event.id);
  const shareRow = element("div", "detail-links");
  const copyButton = element("button", "button-link button-secondary", "Copiar enlace permanente");
  copyButton.type = "button";
  copyButton.addEventListener("click", async () => {
    try {
      await copyText(permalink);
      message.textContent = "Enlace copiado.";
    } catch {
      message.textContent = "No fue posible copiar el enlace. Puedes copiarlo desde la barra del navegador.";
    }
  });
  const shareButton = element("button", "button-link button-secondary", "Compartir");
  shareButton.type = "button";
  shareButton.addEventListener("click", async () => {
    try {
      if (navigator.share) await navigator.share({ title: event.title, url: permalink });
      else {
        await copyText(permalink);
        message.textContent = "Enlace copiado para compartir.";
      }
    } catch (error) {
      if (error?.name !== "AbortError") {
        try {
          await copyText(permalink);
          message.textContent = "No se abrió el menú de compartir; el enlace quedó copiado.";
        } catch {
          message.textContent = "No fue posible compartir ni copiar el enlace.";
        }
      }
    }
  });
  shareRow.append(copyButton, shareButton);
  section.append(shareRow);

  calendarOccurrences(event).forEach((occurrence) => {
    const row = element("div", "calendar-occurrence");
    row.append(element("p", "calendar-occurrence-label", scheduleLabel({ ...event.schedule, start: occurrence.start, occurrences: [] })));
    const actions = element("div", "detail-links");
    const download = element("button", "button-link button-secondary", "Descargar .ics");
    download.type = "button";
    download.addEventListener("click", () => downloadIcs(event, occurrence, permalink));
    const google = externalLink("Añadir a Google Calendar", googleCalendarUrl(event, occurrence, permalink));
    actions.append(download);
    if (google) actions.append(google);
    row.append(actions);
    section.append(row);
  });
  section.append(message);
  return section;
}

function categoryLabels(event) {
  const wrapper = element("div", "category-list");
  (event.categories || []).forEach((category) => {
    if (category?.label) wrapper.append(element("span", "category-label", category.label));
  });
  return wrapper;
}

function verificationLabels(event) {
  const wrapper = element("div", "verification-list");
  publicStatusLabels(event, state.publicationDate).forEach((label) => {
    wrapper.append(element("span", "verification-label", label));
  });
  return wrapper;
}

function eventImage(event, className) {
  const url = safeHttpUrl(event.image?.url);
  if (!url) return null;
  const image = element("img", className);
  image.src = url;
  image.alt = event.image?.alt || "";
  image.loading = "lazy";
  image.addEventListener("error", () => { image.hidden = true; }, { once: true });
  return image;
}

function createCard(event) {
  const card = element("article", "event-card");
  card.dataset.eventId = event.id;
  const image = eventImage(event, "event-card-image");
  if (image) card.append(image);
  const body = element("div", "event-card-body");
  const labels = element("div", "card-labels");
  labels.append(element("span", "type-label", eventTypeLabel(event.event_type)));
  body.append(labels, categoryLabels(event), verificationLabels(event), element("h3", null, event.title));
  const meta = element("dl", "event-meta");
  addMeta(meta, "Cuándo", scheduleLabel(event.schedule));
  addMeta(meta, "Ciudad", event.location?.city);
  addMeta(meta, "Lugar", event.location?.venue);
  addMeta(meta, "Entrada", priceLabel(event.price));
  addMeta(meta, "Organiza", event.organizer);
  body.append(meta);
  if (event.description) body.append(element("p", "event-description", event.description));
  const actions = element("div", "card-actions");
  const detailButton = element("button", "button", "Ver detalles");
  detailButton.type = "button";
  detailButton.addEventListener("click", () => openDetail(event.id, detailButton, true));
  actions.append(detailButton);
  appendPublicLinks(actions, event.links);
  body.append(actions);
  card.append(body);
  return card;
}

function renderEvents(events) {
  elements.grid.replaceChildren();
  events.forEach((event) => elements.grid.append(createCard(event)));
  elements.grid.hidden = events.length === 0;
  elements.noResults.hidden = events.length !== 0;
  elements.resultCount.textContent = `${events.length} ${events.length === 1 ? "resultado" : "resultados"}`;
}

function detailParagraph(label, value) {
  if (value === undefined || value === null || value === "") return null;
  const paragraph = element("p");
  paragraph.append(element("strong", null, `${label}: `), document.createTextNode(String(value)));
  return paragraph;
}

function setEventParam(id, method = "pushState") {
  const params = new URLSearchParams(location.search);
  if (id) params.set("evento", id); else params.delete("evento");
  const query = params.toString();
  history[method](null, "", `${location.pathname}${query ? `?${query}` : ""}${location.hash}`);
}

function openDetail(id, trigger = null, updateUrl = false) {
  const event = findEventById(state.events, id);
  if (!event) {
    setStatus("error", "Actividad no encontrada", "El enlace solicitado ya no está en la agenda. Puedes seguir explorando las demás actividades.");
    return false;
  }
  hideStatus();
  state.detailTrigger = trigger || document.activeElement;
  const content = document.createDocumentFragment();
  const image = eventImage(event, "detail-image");
  if (image) content.append(image);
  content.append(element("span", "type-label", eventTypeLabel(event.event_type)));
  const title = element("h2", null, event.title);
  title.id = "detail-title";
  content.append(title, categoryLabels(event), verificationLabels(event));
  [
    detailParagraph("Cuándo", scheduleLabel(event.schedule)),
    detailParagraph("Ciudad", event.location?.city),
    detailParagraph("Lugar", event.location?.venue),
    detailParagraph("Dirección", event.location?.address),
    detailParagraph("Entrada", priceLabel(event.price)),
    detailParagraph("Organiza", event.organizer),
    detailParagraph("Requisitos", event.registration_requirements),
  ].filter(Boolean).forEach((node) => content.append(node));
  if (event.description) content.append(element("p", "detail-description", event.description));
  if (event.public_status?.advisory_text) {
    content.append(element("p", "verification-advisory", event.public_status.advisory_text));
  }
  const links = element("div", "detail-links");
  appendPublicLinks(links, event.links);
  if (links.childElementCount) content.append(links);
  content.append(calendarAndShareActions(event));
  elements.detailContent.replaceChildren(content);
  if (!elements.dialog.open) elements.dialog.showModal();
  elements.detailClose.focus();
  if (updateUrl && new URLSearchParams(location.search).get("evento") !== id) setEventParam(id);
  return true;
}

function closeDetail(updateUrl = true) {
  if (elements.dialog.open) {
    state.syncingHistory = !updateUrl;
    elements.dialog.close();
  }
  if (updateUrl && new URLSearchParams(location.search).has("evento")) setEventParam(null, "replaceState");
}

function categoryOption(id, label, checked) {
  const wrapper = element("label", "category-choice");
  const input = element("input");
  input.type = "checkbox";
  input.value = id;
  input.checked = checked;
  input.addEventListener("change", () => {
    if (id === "") state.filters.categories = [];
    else if (input.checked) state.filters.categories = [...new Set([...state.filters.categories, id])];
    else state.filters.categories = state.filters.categories.filter((value) => value !== id);
    syncControls();
    applyFilters(true);
  });
  wrapper.append(input, element("span", null, label));
  return wrapper;
}

function buildDynamicFilters() {
  if (!state.cities.some((city) => city.id === state.filters.city)) state.filters.city = "";
  const categoryIds = new Set(state.categories.map((category) => category.id));
  state.filters.categories = state.filters.categories.filter((id) => categoryIds.has(id));
  state.cities.forEach(({ id, label }) => {
    const option = element("option", null, label);
    option.value = id;
    elements.city.append(option);
  });
  elements.categories.replaceChildren(
    categoryOption("", "Todas", state.filters.categories.length === 0),
    ...state.categories.map(({ id, label }) => categoryOption(id, label, state.filters.categories.includes(id))),
  );
}

function readControls() {
  state.filters.query = elements.query.value.trim();
  state.filters.city = elements.city.value;
  state.filters.price = elements.price.value;
  state.filters.period = elements.period.value;
  state.filters.from = elements.from.value;
  state.filters.to = elements.to.value;
}

function syncControls() {
  elements.query.value = state.filters.query;
  elements.city.value = state.cities.some((city) => city.id === state.filters.city) ? state.filters.city : "";
  elements.price.value = state.filters.price;
  elements.period.value = state.filters.period;
  elements.from.value = state.filters.from;
  elements.to.value = state.filters.to;
  elements.range.hidden = state.filters.period !== "rango";
  elements.categories.querySelectorAll("input").forEach((input) => {
    input.checked = input.value === "" ? state.filters.categories.length === 0 : state.filters.categories.includes(input.value);
  });
}

function chip(label, remove) {
  const button = element("button", "filter-chip", label);
  button.type = "button";
  button.setAttribute("aria-label", `Quitar filtro ${label}`);
  button.addEventListener("click", remove);
  return button;
}

function renderChips() {
  const nodes = [];
  if (state.filters.query) nodes.push(chip(`Búsqueda: ${state.filters.query}`, () => removeFilter("query")));
  const city = state.cities.find((item) => item.id === state.filters.city);
  if (city) nodes.push(chip(city.label, () => removeFilter("city")));
  state.filters.categories.forEach((id) => {
    const category = state.categories.find((item) => item.id === id);
    if (category) nodes.push(chip(category.label, () => removeCategory(id)));
  });
  const priceLabels = { gratis: "Gratis", pagado: "Pagado", desconocido: "Precio por confirmar" };
  if (priceLabels[state.filters.price]) nodes.push(chip(priceLabels[state.filters.price], () => removeFilter("price", "todos")));
  const periodLabels = { hoy: "Hoy", manana: "Mañana", "fin-de-semana": "Este fin de semana", rango: "Rango personalizado" };
  if (periodLabels[state.filters.period]) nodes.push(chip(periodLabels[state.filters.period], () => removeFilter("period", "todos")));
  if (state.filters.period === "rango" && state.filters.from) nodes.push(chip(`Desde ${state.filters.from}`, () => removeFilter("from")));
  if (state.filters.period === "rango" && state.filters.to) nodes.push(chip(`Hasta ${state.filters.to}`, () => removeFilter("to")));
  elements.chips.replaceChildren(...nodes);
}

function removeFilter(name, value = "") {
  state.filters[name] = value;
  syncControls();
  applyFilters(true);
}

function removeCategory(id) {
  state.filters.categories = state.filters.categories.filter((value) => value !== id);
  syncControls();
  applyFilters(true);
}

function applyFilters(updateUrl = false) {
  const filtered = filterEvents(state.events, state.filters);
  const section = AGENDA_SECTIONS.find(({ id }) => id === state.section);
  const sectionEvents = eventsForSection(filtered, state.section);
  elements.resultsTitle.textContent = section?.label || "Próximos eventos";
  renderSectionNavigation(filtered);
  renderEvents(sectionEvents);
  renderChips();
  if (updateUrl) {
    const params = filtersToSearchParams(state.filters, location.search);
    const query = params.toString();
    history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}${location.hash}`);
  }
}

function clearFilters() {
  state.filters = filtersFromSearchParams(clearFilterParams(location.search));
  syncControls();
  applyFilters(true);
}

[elements.query, elements.city, elements.price, elements.period, elements.from, elements.to].forEach((control) => {
  control.addEventListener(control === elements.query ? "input" : "change", () => {
    readControls();
    syncControls();
    applyFilters(true);
  });
});
elements.clear.addEventListener("click", clearFilters);
elements.noResultsClear.addEventListener("click", clearFilters);
elements.detailClose.addEventListener("click", () => closeDetail(true));
elements.dialog.addEventListener("click", (event) => {
  if (event.target === elements.dialog) closeDetail(true);
});
elements.dialog.addEventListener("close", () => {
  if (!state.syncingHistory && new URLSearchParams(location.search).has("evento")) setEventParam(null, "replaceState");
  state.syncingHistory = false;
  if (state.detailTrigger instanceof HTMLElement) state.detailTrigger.focus();
  state.detailTrigger = null;
});

window.addEventListener("popstate", () => {
  state.filters = filtersFromSearchParams(location.search);
  state.section = sectionFromLocation(location.search, location.hash);
  syncControls();
  applyFilters(false);
  const id = new URLSearchParams(location.search).get("evento");
  if (id) openDetail(id, null, false); else closeDetail(false);
});

async function initialize() {
  setStatus("loading", "Cargando agenda", "Estamos preparando las actividades disponibles.");
  try {
    const dataset = await fetchDataset();
    state.events = dataset.events;
    state.publicationDate = dataset.publication_date || String(dataset.generated_at || "").slice(0, 10);
    state.categories = collectCategories(dataset.events);
    state.cities = collectCities(dataset.events);
    elements.publicCount.textContent = String(dataset.events.length);
    elements.updated.textContent = formatGeneratedAt(dataset.generated_at);
    try {
      renderChanges(await fetchChangesDataset());
    } catch {
      elements.changes.hidden = true;
    }
    if (!dataset.events.length) {
      elements.results.hidden = true;
      setStatus("empty", "Agenda disponible, sin actividades", "El dataset es válido, pero todavía no contiene actividades públicas.");
      return;
    }
    buildDynamicFilters();
    syncControls();
    applyFilters(false);
    hideStatus();
    elements.results.hidden = false;
    const requestedEvent = new URLSearchParams(location.search).get("evento");
    if (requestedEvent) openDetail(requestedEvent, null, false);
  } catch (error) {
    elements.results.hidden = true;
    const incompatible = error?.code === "incompatible";
    setStatus(
      "error",
      incompatible ? "Dataset incompatible" : "No pudimos cargar la agenda",
      error?.message || "Ocurrió un error inesperado al leer el archivo público.",
    );
  }
}

initialize();
