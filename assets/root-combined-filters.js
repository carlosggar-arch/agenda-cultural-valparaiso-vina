import {
  filterRootEvents,
  rootEventMatchesAdvancedFilters,
  rootEventPublicCategories,
} from "./root-combined-filter-core.mjs?v=20260820-category-merge2";

const DATASET_PATH = "./agenda_web.json";
const form = document.querySelector("[data-filter-form]");
const grid = document.querySelector("[data-event-grid]");
const resultLine = document.querySelector("[data-result-line]");
const empty = document.querySelector("[data-empty]");
const legacyQuery = document.querySelector("[data-filter-query]");
const legacyCategory = document.querySelector("[data-filter-category]");
const legacyFree = document.querySelector("[data-filter-free]");
const headerQuery = document.querySelector("[data-header-query]");
const mobileQuery = document.querySelector("[data-mobile-query]");
const topCategory = document.querySelector("[data-top-category]");
const heroTotal = document.querySelector("[data-total]");

if (!form || !grid || !legacyQuery || !legacyCategory) {
  // Root agenda shell is not present on this page.
} else {
  const state = {
    dataset: [],
    byId: new Map(),
    query: "",
    categories: new Set(),
    access: "todos",
    format: "todos",
    audience: "todos",
    price: "todos",
    applying: false,
  };

  const style = document.createElement("link");
  style.rel = "stylesheet";
  style.href = "./assets/root-combined-filters.css?v=20260817";
  document.head.append(style);

  const advanced = document.createElement("section");
  advanced.className = "advanced-filter-panel";
  advanced.setAttribute("aria-label", "Búsqueda y filtros combinados avanzados");
  advanced.innerHTML = `
    <div class="advanced-search-row">
      <label class="filter-field advanced-search-field">
        <span>Búsqueda inteligente</span>
        <input type="search" data-advanced-query placeholder="Prueba: jazz Valpo, familiar gratis, teatro Viña…" autocomplete="off">
      </label>
      <p class="advanced-search-help">Puedes escribir varias palabras. La búsqueda ignora tildes y entiende términos como Valpo, entradas, inscripción, online o familiar.</p>
    </div>
    <div class="advanced-dimensions">
      <fieldset><legend>Acceso</legend><div class="advanced-choice-row" data-advanced-access>
        <button type="button" data-value="todos" aria-pressed="true">Cualquiera</button>
        <button type="button" data-value="entradas" aria-pressed="false">Con entradas</button>
        <button type="button" data-value="inscripcion" aria-pressed="false">Con inscripción</button>
      </div></fieldset>
      <fieldset><legend>Formato</legend><div class="advanced-choice-row" data-advanced-format>
        <button type="button" data-value="todos" aria-pressed="true">Cualquiera</button>
        <button type="button" data-value="presencial" aria-pressed="false">Presencial</button>
        <button type="button" data-value="en-linea" aria-pressed="false">En línea</button>
      </div></fieldset>
      <fieldset><legend>Público</legend><div class="advanced-choice-row" data-advanced-audience>
        <button type="button" data-value="todos" aria-pressed="true">Cualquiera</button>
        <button type="button" data-value="familiar" aria-pressed="false">Familias</button>
      </div></fieldset>
      <fieldset><legend>Precio</legend><div class="advanced-choice-row" data-advanced-price>
        <button type="button" data-value="todos" aria-pressed="true">Cualquiera</button>
        <button type="button" data-value="gratis" aria-pressed="false">Gratis</button>
        <button type="button" data-value="pagado" aria-pressed="false">De pago</button>
      </div></fieldset>
    </div>
    <div class="advanced-category-panel">
      <div><strong>Categorías</strong><small> Puedes seleccionar varias; entre categorías se aplica “cualquiera de estas”.</small></div>
      <div class="advanced-category-list" data-advanced-categories></div>
    </div>
    <div class="advanced-active" data-advanced-active hidden><span>Filtros activos:</span><div data-advanced-chips></div></div>
  `;

  legacyQuery.closest("label")?.classList.add("legacy-advanced-hidden");
  legacyCategory.closest("label")?.classList.add("legacy-advanced-hidden");
  legacyFree?.closest("label")?.classList.add("legacy-advanced-hidden");
  form.querySelector(".filter-title-row")?.after(advanced);

  const query = advanced.querySelector("[data-advanced-query]");
  const categoryList = advanced.querySelector("[data-advanced-categories]");
  const active = advanced.querySelector("[data-advanced-active]");
  const chips = advanced.querySelector("[data-advanced-chips]");

  function publicEvent(event) {
    const categories = rootEventPublicCategories(event);
    return {
      ...event,
      categories,
      primary_category: categories[0] || event?.primary_category,
    };
  }

  function categoryCatalog() {
    const categories = new Map();
    for (const event of state.dataset) {
      for (const category of event.categories || []) {
        if (!category?.id) continue;
        const current = categories.get(category.id) || { id: category.id, label: category.label || category.id, count: 0 };
        current.count += 1;
        categories.set(category.id, current);
      }
    }
    return [...categories.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "es-CL"));
  }

  function renderCategories() {
    categoryList.replaceChildren();
    for (const category of categoryCatalog()) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.category = category.id;
      button.setAttribute("aria-pressed", String(state.categories.has(category.id)));
      button.innerHTML = `<span>${category.label}</span><small>${category.count}</small>`;
      button.addEventListener("click", () => {
        if (state.categories.has(category.id)) state.categories.delete(category.id);
        else state.categories.add(category.id);
        renderAdvancedState();
      });
      categoryList.append(button);
    }
  }

  function setPressed(groupName, value) {
    advanced.querySelectorAll(`[data-advanced-${groupName}] [data-value]`).forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.value === value));
    });
  }

  function updateUrl() {
    const url = new URL(location.href);
    const setOrDelete = (key, value, empty = "todos") => {
      if (!value || value === empty) url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    };
    setOrDelete("q", state.query, "");
    setOrDelete("cat", [...state.categories].sort().join(","), "");
    setOrDelete("access", state.access);
    setOrDelete("format", state.format);
    setOrDelete("aud", state.audience);
    setOrDelete("price", state.price);
    history.replaceState({}, "", url);
  }

  function currentAdvancedFilters() {
    return {
      query: state.query,
      categories: state.categories,
      access: state.access,
      format: state.format,
      audience: state.audience,
      price: state.price,
    };
  }

  function visibleBaseCards() {
    return [...grid.querySelectorAll(".event-card")];
  }

  function matchesCorrectedQuickSection(event) {
    const active = document.querySelector('[data-top-section][aria-pressed="true"]')?.dataset.topSection || "";
    if (active === "talleres-cursos") {
      return rootEventPublicCategories(event).some((category) => category?.id === "cursos-talleres");
    }
    return true;
  }

  function applyAdvancedFilters() {
    if (state.applying) return;
    state.applying = true;
    try {
      let visible = 0;
      for (const card of visibleBaseCards()) {
        const event = state.byId.get(card.dataset.eventId);
        const matches = event ? matchesCorrectedQuickSection(event) && rootEventMatchesAdvancedFilters(event, currentAdvancedFilters()) : true;
        card.hidden = !matches;
        if (matches) visible += 1;
      }
      const baseCount = visibleBaseCards().length;
      if (resultLine) {
        const suffix = state.query ? ` para “${state.query}”` : "";
        resultLine.textContent = `${visible} ${visible === 1 ? "actividad" : "actividades"}${suffix}.`;
      }
      if (heroTotal) heroTotal.textContent = String(visible);
      if (empty) empty.hidden = visible > 0;
      advanced.dataset.visibleResults = String(visible);
      advanced.dataset.baseResults = String(baseCount);
      updateUrl();
    } finally {
      state.applying = false;
    }
  }

  function renderChips() {
    chips.replaceChildren();
    const items = [];
    if (state.query) items.push([`Búsqueda: ${state.query}`, () => { state.query = ""; query.value = ""; }]);
    const labels = new Map(categoryCatalog().map((item) => [item.id, item.label]));
    for (const category of state.categories) items.push([labels.get(category) || category, () => state.categories.delete(category)]);
    if (state.access !== "todos") items.push([state.access === "entradas" ? "Con entradas" : "Con inscripción", () => { state.access = "todos"; }]);
    if (state.format !== "todos") items.push([state.format === "en-linea" ? "En línea" : "Presencial", () => { state.format = "todos"; }]);
    if (state.audience !== "todos") items.push(["Para familias", () => { state.audience = "todos"; }]);
    if (state.price !== "todos") items.push([state.price === "gratis" ? "Gratis" : "De pago", () => { state.price = "todos"; }]);
    active.hidden = items.length === 0;
    for (const [label, remove] of items) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${label} ×`;
      button.addEventListener("click", () => { remove(); renderAdvancedState(); });
      chips.append(button);
    }
  }

  function renderAdvancedState() {
    setPressed("access", state.access);
    setPressed("format", state.format);
    setPressed("audience", state.audience);
    setPressed("price", state.price);
    categoryList.querySelectorAll("[data-category]").forEach((button) => {
      button.setAttribute("aria-pressed", String(state.categories.has(button.dataset.category)));
    });
    renderChips();
    applyAdvancedFilters();
  }

  function clearLegacyAdvancedHooks() {
    let changed = false;
    if (legacyQuery.value) { legacyQuery.value = ""; changed = true; }
    if (legacyCategory.value) { legacyCategory.value = ""; changed = true; }
    if (legacyFree?.checked) { legacyFree.checked = false; changed = true; }
    return changed;
  }

  function requestBaseRerender() {
    clearLegacyAdvancedHooks();
    legacyQuery.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function setExternalCategories(values) {
    state.categories = new Set((values || []).filter(Boolean));
    requestAnimationFrame(() => {
      requestBaseRerender();
      renderAdvancedState();
    });
  }

  globalThis.__VIVAMOS_ROOT_FILTERS__ = {
    setCategories: setExternalCategories,
    getCategories: () => [...state.categories],
    apply: () => requestAnimationFrame(renderAdvancedState),
  };

  function absorbLegacyCategory() {
    const value = legacyCategory.value;
    if (!value) return false;
    state.categories.clear();
    state.categories.add(value);
    legacyCategory.value = "";
    renderAdvancedState();
    return true;
  }

  function bindChoice(name, stateKey) {
    advanced.querySelector(`[data-advanced-${name}]`)?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-value]");
      if (!button) return;
      state[stateKey] = button.dataset.value;
      renderAdvancedState();
    });
  }

  bindChoice("access", "access");
  bindChoice("format", "format");
  bindChoice("audience", "audience");
  bindChoice("price", "price");

  query.addEventListener("input", () => {
    state.query = query.value.trim();
    if (headerQuery && headerQuery.value !== query.value) headerQuery.value = query.value;
    if (mobileQuery && mobileQuery.value !== query.value) mobileQuery.value = query.value;
    renderAdvancedState();
  });

  for (const externalQuery of [headerQuery, mobileQuery]) {
    externalQuery?.addEventListener("input", () => {
      state.query = externalQuery.value.trim();
      query.value = externalQuery.value;
      requestAnimationFrame(() => {
        requestBaseRerender();
        renderAdvancedState();
      });
    });
  }

  topCategory?.addEventListener("change", () => {
    if (!topCategory.value) state.categories.clear();
    else {
      state.categories.clear();
      state.categories.add(topCategory.value);
    }
    requestAnimationFrame(() => {
      clearLegacyAdvancedHooks();
      requestBaseRerender();
      renderAdvancedState();
    });
  });

  document.querySelector("[data-filter-clear]")?.addEventListener("click", () => {
    state.query = "";
    state.categories.clear();
    state.access = "todos";
    state.format = "todos";
    state.audience = "todos";
    state.price = "todos";
    query.value = "";
    if (headerQuery) headerQuery.value = "";
    if (mobileQuery) mobileQuery.value = "";
    requestAnimationFrame(renderAdvancedState);
  });

  document.querySelector("[data-empty-clear]")?.addEventListener("click", () => {
    state.query = "";
    state.categories.clear();
    state.access = "todos";
    state.format = "todos";
    state.audience = "todos";
    state.price = "todos";
    query.value = "";
    requestAnimationFrame(renderAdvancedState);
  });

  const observer = new MutationObserver(() => {
    if (state.applying) return;
    if (absorbLegacyCategory()) {
      requestAnimationFrame(requestBaseRerender);
      return;
    }
    requestAnimationFrame(applyAdvancedFilters);
  });
  observer.observe(grid, { childList: true });

  function restoreAdvancedUrl() {
    const params = new URLSearchParams(location.search);
    state.query = params.get("q") || "";
    state.categories = new Set((params.get("cat") || params.get("categoria") || "").split(",").map((item) => item.trim()).filter(Boolean));
    state.access = ["todos", "entradas", "inscripcion"].includes(params.get("access")) ? params.get("access") : "todos";
    state.format = ["todos", "presencial", "en-linea"].includes(params.get("format")) ? params.get("format") : "todos";
    state.audience = ["todos", "familiar"].includes(params.get("aud")) ? params.get("aud") : "todos";
    state.price = ["todos", "gratis", "pagado"].includes(params.get("price")) ? params.get("price") : (params.get("gratis") === "true" ? "gratis" : "todos");
    query.value = state.query;
    if (headerQuery) headerQuery.value = state.query;
    if (mobileQuery) mobileQuery.value = state.query;
    clearLegacyAdvancedHooks();
  }

  async function initializeAdvancedFilters() {
    try {
      const response = await fetch(DATASET_PATH, { headers: { Accept: "application/json" } });
      if (!response.ok) return;
      const dataset = await response.json();
      state.dataset = Array.isArray(dataset.events) ? dataset.events.map(publicEvent) : [];
      state.byId = new Map(state.dataset.map((event) => [event.id, event]));
      restoreAdvancedUrl();
      renderCategories();
      requestBaseRerender();
      renderAdvancedState();
      advanced.dataset.ready = "true";
    } catch {
      advanced.dataset.ready = "false";
    }
  }

  initializeAdvancedFilters();
}
