export const SOURCES_PATH = "./fuentes_publicas.json";

export function normalizeText(value) {
  return String(value || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("es");
}

export function filterSources(sources, filters = {}) {
  const query = normalizeText(filters.query);
  return sources.filter((source) => {
    const searchable = normalizeText([source.name, source.source_type, ...source.categories].join(" "));
    if (query && !searchable.includes(query)) return false;
    if (filters.city === "ambas" && source.cities.length < 2) return false;
    if (filters.city && filters.city !== "ambas" && !source.cities.includes(filters.city)) return false;
    if (filters.type && source.source_type !== filters.type) return false;
    return !(filters.category && !source.categories.includes(filters.category));
  });
}

export function collectOptions(sources, field) {
  return [...new Set(sources.flatMap((source) => source[field] || []))].sort((a, b) => a.localeCompare(b, "es"));
}

export function safeExternalUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

export function validateSourcesDataset(data) {
  if (!data || data.schema_version !== "1.0.0" || !Array.isArray(data.sources)) throw new Error("Formato incompatible.");
  const ids = new Set();
  data.sources.forEach((source) => {
    if (!source.id?.startsWith("fuente_") || ids.has(source.id) || !source.name || !safeExternalUrl(source.website_url)
      || source.public_status !== "integrada" || !source.cities?.length || !source.categories?.length || !source.source_type) {
      throw new Error("Fuente inválida.");
    }
    ids.add(source.id);
  });
  return data;
}

const dom = typeof document === "undefined" ? {} : {
  form: document.querySelector("[data-sources-form]"), query: document.querySelector("[data-source-query]"),
  city: document.querySelector("[data-source-city]"), type: document.querySelector("[data-source-type]"),
  category: document.querySelector("[data-source-category]"), total: document.querySelector("[data-source-total]"),
  updated: document.querySelector("[data-source-updated]"), result: document.querySelector("[data-source-result]"),
  grid: document.querySelector("[data-sources-grid]"), empty: document.querySelector("[data-sources-empty]"),
  error: document.querySelector("[data-sources-error]"),
};
let allSources = [];

function element(tag, className, text) {
  const node = document.createElement(tag); if (className) node.className = className;
  if (text !== undefined) node.textContent = text; return node;
}

function renderCard(source) {
  const article = element("article", "source-card");
  const categories = element("ul", "source-categories");
  source.categories.forEach((category) => categories.append(element("li", "", category)));
  const link = element("a", "source-link", "Visitar sitio oficial ↗");
  link.href = safeExternalUrl(source.website_url); link.target = "_blank"; link.rel = "noopener noreferrer";
  article.append(element("span", "source-status", "Integrada"), element("h2", "", source.name),
    element("p", "source-meta", `${source.source_type} · ${source.cities.join(", ")}`), categories);
  if (source.last_verified_at) article.append(element("p", "source-verified", `Última verificación: ${source.last_verified_at}`));
  article.append(link); return article;
}

function render() {
  const visible = filterSources(allSources, { query: dom.query.value, city: dom.city.value, type: dom.type.value, category: dom.category.value });
  dom.grid.replaceChildren(...visible.map(renderCard)); dom.result.textContent = `${visible.length} de ${allSources.length} fuentes visibles`;
  dom.empty.hidden = visible.length !== 0;
}

function addOptions(select, values) { values.forEach((value) => select.add(new Option(value, value))); }

async function init() {
  if (!dom.form) return;
  try {
    const response = await fetch(SOURCES_PATH, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const dataset = validateSourcesDataset(await response.json()); allSources = dataset.sources;
    dom.total.textContent = String(allSources.length);
    dom.updated.textContent = `Actualizado el ${new Date(dataset.generated_at).toLocaleDateString("es-CL")}`;
    addOptions(dom.type, collectOptions(allSources, "source_type")); addOptions(dom.category, collectOptions(allSources, "categories")); render();
  } catch {
    dom.error.hidden = false; dom.error.textContent = "No fue posible cargar las fuentes. Inténtalo nuevamente más tarde.";
  }
}
dom.form?.addEventListener("input", render); dom.form?.addEventListener("change", render);
dom.form?.addEventListener("reset", () => setTimeout(render)); init();
