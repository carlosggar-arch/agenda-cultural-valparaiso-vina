const sourcesSection = document.querySelector("[data-sources-section]");
const sourcesGrid = document.querySelector("[data-sources-grid]");
const sourcesTotal = document.querySelector("[data-sources-total]");
const footer = document.querySelector("footer");

const DATASETS = Object.freeze({
  valparaiso: "../agenda_web.json",
  gijon: "./data/gijon/agenda_web.json",
});

const PUBLIC_CATALOGUES = Object.freeze({
  valparaiso: "../fuentes_publicas.json",
});

let configuredSources = [];
let authoritativeCatalogue = false;
let loadGeneration = 0;

function sourceKey(value) {
  return String(value || "").trim().toLocaleLowerCase(document.documentElement.lang || "es");
}

function sourceId(value) {
  return String(value || "").trim().toLocaleLowerCase("en");
}

function safeHttpUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function finiteMetric(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function sourceDiagnosticText(source) {
  const diagnostic = source?.diagnostics;
  if (!diagnostic || typeof diagnostic !== "object") return "";

  const pieces = [];
  const reviewedItems = finiteMetric(diagnostic.reviewed_items);
  const reviewedTitles = finiteMetric(diagnostic.reviewed_titles);
  const datedCandidates = finiteMetric(diagnostic.dated_candidates);
  const sessionsDetected = finiteMetric(diagnostic.sessions_detected);
  const publishedEvents = finiteMetric(diagnostic.published_events);
  const sessionsPublished = finiteMetric(diagnostic.sessions_published);
  const filtered = finiteMetric(diagnostic.filtered_or_deduplicated);
  const withoutTime = finiteMetric(diagnostic.without_start_time);

  if (reviewedItems !== null) pieces.push(`${reviewedItems} revisados`);
  else if (reviewedTitles !== null) pieces.push(`${reviewedTitles} títulos revisados`);

  if (datedCandidates !== null) pieces.push(`${datedCandidates} candidatos con fecha`);
  else if (sessionsDetected !== null) pieces.push(`${sessionsDetected} sesiones detectadas`);

  if (publishedEvents !== null) pieces.push(`${publishedEvents} publicados`);
  else if (sessionsPublished !== null) pieces.push(`${sessionsPublished} sesiones publicadas`);

  if (filtered !== null) pieces.push(`${filtered} filtrados/duplicados`);
  if (withoutTime !== null) pieces.push(`${withoutTime} sin hora de inicio`);

  return pieces.join(" · ");
}

function appendDiagnostic(card, source) {
  if (!card || card.querySelector(".source-diagnostics")) return;
  const text = sourceDiagnosticText(source);
  if (!text) return;

  const diagnostic = document.createElement("small");
  diagnostic.className = "source-diagnostics";
  diagnostic.textContent = text;
  card.append(diagnostic);

  const note = String(source?.diagnostics?.note || "").trim();
  if (note) {
    const noteNode = document.createElement("small");
    noteNode.className = "source-diagnostics-note";
    noteNode.textContent = note;
    card.append(noteNode);
  }
}

function gridSourceCards() {
  const cards = new Map();
  if (!sourcesGrid) return cards;
  for (const card of sourcesGrid.querySelectorAll(".source-card")) {
    const name = card.querySelector("strong")?.textContent;
    if (name) cards.set(sourceKey(name), card);
  }
  return cards;
}

function gridSourceNames() {
  return new Set(gridSourceCards().keys());
}

function configuredSourceCard(source) {
  const card = document.createElement("article");
  card.className = "source-card source-card--catalog";
  card.dataset.catalogSourceId = String(source?.id || "");
  if (source?.canonical_source_id) card.dataset.canonicalSourceId = String(source.canonical_source_id);

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

  appendDiagnostic(card, source);

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

  let cards = gridSourceCards();
  let changed = false;

  if (authoritativeCatalogue) {
    const allowed = new Set(configuredSources.map((source) => sourceKey(source?.name)).filter(Boolean));
    for (const [key, card] of cards) {
      if (allowed.has(key)) continue;
      card.remove();
      changed = true;
    }
    cards = gridSourceCards();
  }

  for (const source of configuredSources) {
    const name = String(source?.name || "").trim();
    if (!name) continue;
    const key = sourceKey(name);
    const existing = cards.get(key);
    if (existing) {
      appendDiagnostic(existing, source);
      continue;
    }
    const card = configuredSourceCard(source);
    sourcesGrid.append(card);
    cards.set(key, card);
    changed = true;
  }

  if (changed || sourcesGrid.children.length) sourcesSection.hidden = false;
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

function sourcesFromDataset(dataset) {
  const sources = Array.isArray(dataset?.sources)
    ? dataset.sources.filter((source) => source && source.name).map((source) => ({ ...source }))
    : [];
  const byId = new Map(sources.map((source) => [sourceId(source?.id), source]));

  for (const [id, diagnostics] of Object.entries(dataset?.source_diagnostics || {})) {
    if (!diagnostics || typeof diagnostics !== "object") continue;
    const existing = byId.get(sourceId(id));
    if (existing) existing.diagnostics = diagnostics;
  }
  return sources;
}

function eventCountsBySourceId(dataset) {
  const counts = new Map();
  for (const event of dataset?.events || []) {
    const id = sourceId(event?.source_id);
    if (!id) continue;
    counts.set(id, (counts.get(id) || 0) + 1);
  }
  return counts;
}

function sourcesFromPublicCatalogue(catalogue, dataset, datasetSources = []) {
  const publicSources = Array.isArray(catalogue?.sources) ? catalogue.sources : [];
  const runtimeById = new Map(datasetSources.map((source) => [sourceId(source?.id), source]));
  const runtimeByName = new Map(datasetSources.map((source) => [sourceKey(source?.name), source]));
  const eventCounts = eventCountsBySourceId(dataset);
  const diagnosticsById = dataset?.source_diagnostics || {};

  return publicSources
    .filter((source) => source && source.name && source.public_status === "integrada")
    .map((source) => {
      const canonicalId = sourceId(source.canonical_source_id);
      const runtime = (canonicalId && runtimeById.get(canonicalId)) || runtimeByName.get(sourceKey(source.name));
      const directCount = canonicalId ? eventCounts.get(canonicalId) : undefined;
      const diagnostics = (canonicalId && diagnosticsById[canonicalId]) || runtime?.diagnostics;
      return {
        id: source.id,
        canonical_source_id: canonicalId || null,
        name: source.name,
        url: source.website_url,
        scope: Array.isArray(source.cities) ? source.cities.join(" / ") : "",
        official: runtime?.official === true,
        event_count: Number(directCount ?? runtime?.event_count ?? 0),
        diagnostics,
      };
    });
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function loadConfiguredSources() {
  const generation = ++loadGeneration;
  configuredSources = [];
  authoritativeCatalogue = false;
  const city = document.documentElement.dataset.city || "valparaiso";
  const datasetUrl = DATASETS[city];
  if (!datasetUrl) {
    mergeConfiguredSourcesIntoGrid();
    return;
  }

  try {
    const dataset = await fetchJson(datasetUrl);
    if (generation !== loadGeneration) return;
    const datasetSources = sourcesFromDataset(dataset);
    const catalogueUrl = PUBLIC_CATALOGUES[city];

    if (catalogueUrl) {
      try {
        const catalogue = await fetchJson(catalogueUrl);
        if (generation !== loadGeneration) return;
        configuredSources = sourcesFromPublicCatalogue(catalogue, dataset, datasetSources);
        authoritativeCatalogue = configuredSources.length > 0;
      } catch {
        configuredSources = datasetSources;
      }
    } else {
      configuredSources = datasetSources;
    }
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
    .source-diagnostics{display:block;margin-top:.35rem;font-weight:700;color:var(--brand,#153e52)}
    .source-diagnostics-note{display:block;margin-top:.18rem;color:var(--muted,#64726f);line-height:1.35}
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