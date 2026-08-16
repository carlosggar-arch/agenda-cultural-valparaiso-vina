const sourcesSection = document.querySelector("[data-sources-section]");
const sourcesGrid = document.querySelector("[data-sources-grid]");
const sourcesTotal = document.querySelector("[data-sources-total]");
const footer = document.querySelector("footer");

const DATASETS = Object.freeze({
  valparaiso: "../agenda_web.json",
  gijon: "./data/gijon/agenda_web.json",
});

let configuredSources = [];
let loadGeneration = 0;

function sourceKey(value) {
  return String(value || "").trim().toLocaleLowerCase(document.documentElement.lang || "es");
}

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function gridSourceNames() {
  const names = new Set();
  if (!sourcesGrid) return names;
  for (const card of sourcesGrid.querySelectorAll(".source-card")) {
    const name = card.querySelector("strong")?.textContent;
    if (name) names.add(sourceKey(name));
  }
  return names;
}

function configuredSourceCard(source) {
  const card = document.createElement("article");
  card.className = "source-card source-card--catalog";
  card.dataset.catalogSourceId = String(source?.id || "");

  const heading = document.createElement("div");
  heading.className = "source-card-heading";

  const name = document.createElement("strong");
  name.textContent = String(source?.name || "Fuente");
  heading.append(name);

  if (source?.official === true) {
    const badge = document.createElement("span");
    badge.className = "source-official-badge";
    badge.textContent = "Oficial";
    heading.append(badge);
  }
  card.append(heading);

  const count = Number(source?.event_count || 0);
  const status = document.createElement("small");
  status.textContent = count > 0
    ? `${count} ${count === 1 ? "actividad" : "actividades"} en esta agenda`
    : "Fuente incorporada · sin eventos importados en esta ejecución";
  card.append(status);

  const scope = String(source?.scope || "").trim();
  if (scope) {
    const scopeNode = document.createElement("small");
    scopeNode.className = "source-scope";
    scopeNode.textContent = `Ámbito: ${scope}`;
    card.append(scopeNode);
  }

  const href = safeHttpUrl(source?.url);
  if (href) {
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Abrir referencia →";
    card.append(link);
  }
  return card;
}

function mergeConfiguredSourcesIntoGrid() {
  if (!sourcesGrid || !sourcesSection || !configuredSources.length) {
    updateSourceCount();
    return;
  }

  const present = gridSourceNames();
  let appended = false;
  for (const source of configuredSources) {
    const name = String(source?.name || "").trim();
    if (!name || present.has(sourceKey(name))) continue;
    sourcesGrid.append(configuredSourceCard(source));
    present.add(sourceKey(name));
    appended = true;
  }

  if (appended || sourcesGrid.children.length) sourcesSection.hidden = false;
  updateSourceCount();
}

function updateSourceCount() {
  if (!sourcesGrid) return;
  const count = gridSourceNames().size;
  if (sourcesTotal) sourcesTotal.textContent = String(count);
  if (!button) return;
  const opening = sourcesSection?.classList.contains("sources-user-open");
  button.textContent = opening
    ? `Ocultar fuentes${count ? ` · ${count}` : ""}`
    : `Fuentes${count ? ` · ${count}` : ""}`;
}

async function loadConfiguredSources() {
  const generation = ++loadGeneration;
  configuredSources = [];
  const city = document.documentElement.dataset.city || "valparaiso";
  const datasetUrl = DATASETS[city];
  if (!datasetUrl) {
    mergeConfiguredSourcesIntoGrid();
    return;
  }

  try {
    const response = await fetch(datasetUrl, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const dataset = await response.json();
    if (generation !== loadGeneration) return;
    configuredSources = Array.isArray(dataset?.sources)
      ? dataset.sources.filter((source) => source && source.name)
      : [];
  } catch {
    if (generation !== loadGeneration) return;
    configuredSources = [];
  }
  mergeConfiguredSourcesIntoGrid();
}

let button = null;

if (sourcesSection && sourcesGrid && footer) {
  sourcesSection.id = "agenda-sources";

  const style = document.createElement("style");
  style.textContent = `
    [data-sources-section]:not(.sources-user-open){display:none!important}
    .sources-toggle{border:1px solid color-mix(in srgb,var(--brand) 24%,#fff);background:#fff;color:var(--brand);border-radius:999px;padding:.5rem .8rem;font-weight:800;cursor:pointer}
    .sources-toggle:hover,.sources-toggle:focus-visible{border-color:var(--accent)}
    .source-card--catalog .source-scope{display:block;margin-top:.12rem;color:var(--muted,#64726f)}
  `;
  document.head.append(style);

  button = document.createElement("button");
  button.type = "button";
  button.className = "sources-toggle";
  button.dataset.sourcesToggle = "";
  button.setAttribute("aria-controls", "agenda-sources");
  button.setAttribute("aria-expanded", "false");
  button.textContent = "Fuentes";
  footer.append(button);

  button.addEventListener("click", () => {
    const opening = !sourcesSection.classList.contains("sources-user-open");
    sourcesSection.classList.toggle("sources-user-open", opening);
    button.setAttribute("aria-expanded", opening ? "true" : "false");
    updateSourceCount();
    if (opening) sourcesSection.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  new MutationObserver(() => queueMicrotask(mergeConfiguredSourcesIntoGrid)).observe(sourcesGrid, {
    childList: true,
  });

  new MutationObserver(loadConfiguredSources).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-city"],
  });

  loadConfiguredSources();
  updateSourceCount();
}
