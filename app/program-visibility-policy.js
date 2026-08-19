const PROGRAM_TYPE = "program";
const MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre";

let latestSecondaryPrograms = [];
let renderQueued = false;
let shellReady = false;
let observer = null;

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function fold(value) {
  return clean(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), globalThis.location?.href || "https://example.invalid/");
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function sourceIds(events) {
  return new Set(
    (events || [])
      .filter((event) => event?.event_type !== PROGRAM_TYPE)
      .map((event) => clean(event?.source_id))
      .filter(Boolean),
  );
}

export function isProgramCovered(program, concreteEvents) {
  const covered = Array.isArray(program?.editorial?.covered_source_ids)
    ? program.editorial.covered_source_ids.map(clean).filter(Boolean)
    : [];
  if (!covered.length) return false;
  const available = sourceIds(concreteEvents);
  return covered.every((sourceId) => available.has(sourceId));
}

export function partitionPrograms(events) {
  const list = Array.isArray(events) ? events : [];
  const publicEvents = list.filter((event) => event?.event_type !== PROGRAM_TYPE);
  const programs = list.filter((event) => event?.event_type === PROGRAM_TYPE);
  const secondaryPrograms = programs.filter((program) => !isProgramCovered(program, publicEvents));
  const hiddenPrograms = programs.filter((program) => !secondaryPrograms.includes(program));
  return { publicEvents, secondaryPrograms, hiddenPrograms };
}

function recalculateCounts(events, original = {}) {
  return {
    ...original,
    total: events.length,
    events: events.filter((event) => !["program", "flexible_offer", "course"].includes(event?.event_type)).length,
    courses: events.filter((event) => event?.event_type === "course").length,
    flexible_offers: events.filter((event) => event?.event_type === "flexible_offer").length,
    programs: 0,
  };
}

export function applyProgramVisibilityPolicy(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) {
    return { dataset, secondaryPrograms: [], hiddenPrograms: [] };
  }
  const { publicEvents, secondaryPrograms, hiddenPrograms } = partitionPrograms(dataset.events);
  if (!secondaryPrograms.length && !hiddenPrograms.length) {
    return { dataset, secondaryPrograms, hiddenPrograms };
  }
  return {
    dataset: {
      ...dataset,
      events: publicEvents,
      counts: recalculateCounts(publicEvents, dataset.counts),
    },
    secondaryPrograms,
    hiddenPrograms,
  };
}

export function programReferenceTitle(program) {
  const original = clean(program?.title) || "Programación general";
  const monthMatch = original.match(new RegExp(`\\b(${MONTHS})\\b(?:\\s+(20\\d{2}))?`, "i"));
  const genericMatch = original.match(new RegExp(`^(.*?)\\s*(?:[–—-]|:)\\s*(?:cartelera|programaci[oó]n)\\s+(${MONTHS})(?:\\s+(20\\d{2}))?\\s*$`, "i"));
  const fullyGeneric = original.match(new RegExp(`^(?:cartelera|programaci[oó]n)\\s+(${MONTHS})(?:\\s+(20\\d{2}))?\\s*$`, "i"));

  if (!(genericMatch || fullyGeneric)) return original;

  const prefix = clean(genericMatch?.[1]);
  const venue = clean(program?.location?.venue);
  const organizer = clean(program?.organizer);
  const source = clean(program?.source_name);
  let subject = prefix || venue || organizer || source || "Programación";
  const venueLooksLikeAcronym = venue && venue === venue.toLocaleUpperCase("es");
  if (prefix && venue && fold(prefix) === fold(venue) && venueLooksLikeAcronym) subject = venue;

  const month = clean(genericMatch?.[2] || fullyGeneric?.[1] || monthMatch?.[1]).toLocaleLowerCase("es");
  const year = clean(genericMatch?.[3] || fullyGeneric?.[2] || monthMatch?.[2]);
  return `${subject} — programación de ${month}${year ? ` ${year}` : ""}`;
}

function formatDateOnly(value) {
  const key = clean(value).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(key)) return null;
  const [year, month, day] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: "UTC",
    day: "numeric",
    month: "short",
    year: year !== new Date().getFullYear() ? "numeric" : undefined,
  }).format(new Date(Date.UTC(year, month - 1, day, 12)));
}

function periodLabel(program) {
  const start = formatDateOnly(program?.schedule?.start);
  const end = formatDateOnly(program?.schedule?.end);
  if (start && end && start !== end) return `${start} – ${end}`;
  return start || clean(program?.schedule?.display_text) || "Periodo por confirmar";
}

function programSource(program) {
  return clean(program?.source_name || program?.organizer || "Fuente de programación");
}

function programLink(program) {
  return safeHttpUrl(program?.links?.official || program?.links?.source || program?.source_url);
}

function programCard(program) {
  const article = document.createElement("article");
  article.className = "program-reference-card";
  const title = programReferenceTitle(program);
  const venue = clean(program?.location?.venue);
  const city = clean(program?.location?.city);
  const location = [venue, city].filter(Boolean).join(" · ");
  const href = programLink(program);
  article.innerHTML = `
    <div class="program-reference-meta">
      <span>Cartelera</span>
      <span>Referencia</span>
    </div>
    <h4>${escapeHtml(title)}</h4>
    <p class="program-reference-period">${escapeHtml(periodLabel(program))}</p>
    ${location ? `<p>${escapeHtml(location)}</p>` : ""}
    <p class="program-reference-copy">Programación general conservada como respaldo porque todavía no se han podido convertir todas sus citas en eventos individuales con suficiente fiabilidad.</p>
    <p class="program-reference-source">Fuente: <strong>${escapeHtml(programSource(program))}</strong></p>
    ${href ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">Ver programación completa →</a>` : ""}
  `;
  return article;
}

function ensureProgramShell() {
  const section = document.querySelector("[data-program-section]");
  const grid = document.querySelector("[data-program-grid]");
  if (!(section && grid)) return null;

  const heading = section.querySelector(".section-heading");
  const eyebrow = heading?.querySelector(".eyebrow");
  const title = heading?.querySelector("h3");
  const copy = heading?.querySelector("p:not(.eyebrow)");
  const total = section.querySelector("[data-program-total]");
  const countLabel = total?.parentElement;

  if (eyebrow?.textContent !== "Referencia complementaria") eyebrow.textContent = "Referencia complementaria";
  if (title?.textContent !== "Carteleras y programaciones") title.textContent = "Carteleras y programaciones";
  const explanatoryCopy = "Solo aparecen aquí cuando todavía no hemos podido desglosar toda la cartelera en eventos individuales fiables.";
  if (copy?.textContent !== explanatoryCopy) copy.textContent = explanatoryCopy;
  if (countLabel && countLabel.dataset.programCountLabel !== "true") {
    countLabel.replaceChildren(total, document.createTextNode(" carteleras"));
    countLabel.dataset.programCountLabel = "true";
  }

  let details = section.querySelector("details.program-reference-details");
  if (!details) {
    details = document.createElement("details");
    details.className = "program-reference-details";
    const summary = document.createElement("summary");
    summary.className = "program-reference-summary";
    details.append(summary);
    grid.before(details);
    details.append(grid);
  }
  shellReady = true;
  return { section, grid, total, details, summary: details.querySelector("summary") };
}

function programSignature(programs) {
  return programs.map((program) => `${program?.id || ""}|${programReferenceTitle(program)}|${periodLabel(program)}`).join("||");
}

function observeProgramSection() {
  const section = document.querySelector("[data-program-section]");
  if (!section) return;
  if (!observer) observer = new MutationObserver(() => queueRender());
  observer.observe(section, { childList: true, subtree: true, attributes: true, attributeFilter: ["hidden"] });
}

function renderSecondaryPrograms() {
  renderQueued = false;
  observer?.disconnect();
  try {
    const shell = ensureProgramShell();
    if (!shell) return;
    const programs = latestSecondaryPrograms;
    if (!programs.length) {
      if (!shell.section.hidden) shell.section.hidden = true;
      if (shell.grid.childElementCount) shell.grid.replaceChildren();
      shell.grid.dataset.programPolicySignature = "";
      return;
    }

    const signature = programSignature(programs);
    const needsCards = shell.grid.dataset.programPolicySignature !== signature || shell.grid.childElementCount !== programs.length;
    if (needsCards) {
      shell.grid.replaceChildren(...programs.map(programCard));
      shell.grid.dataset.programPolicySignature = signature;
    }
    if (shell.total?.textContent !== String(programs.length)) shell.total.textContent = String(programs.length);
    const summaryText = `Ver ${programs.length} ${programs.length === 1 ? "cartelera de referencia" : "carteleras de referencia"}`;
    if (shell.summary?.textContent !== summaryText) shell.summary.textContent = summaryText;
    if (shell.section.hidden) shell.section.hidden = false;
  } finally {
    observeProgramSection();
  }
}

function queueRender() {
  if (renderQueued) return;
  renderQueued = true;
  queueMicrotask(renderSecondaryPrograms);
}

function installStylesheet() {
  if (document.querySelector('link[data-program-visibility-policy]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./program-visibility-policy.css?v=20260819-programs2";
  link.dataset.programVisibilityPolicy = "true";
  document.head.append(link);
}

function isAgendaDatasetRequest(input, response) {
  const urls = [response?.url, typeof input === "string" ? input : input?.url].filter(Boolean);
  return urls.some((value) => /(?:^|\/)agenda_web\.json(?:[?#]|$)/.test(String(value)));
}

export function installProgramVisibilityPolicy(target = globalThis) {
  if (!target || typeof target.fetch !== "function" || target.__vivamosProgramVisibilityPolicyInstalled) return;
  const upstreamFetch = target.fetch.bind(target);
  target.fetch = async (...args) => {
    const response = await upstreamFetch(...args);
    if (!response?.ok || !isAgendaDatasetRequest(args[0], response)) return response;
    let dataset;
    try { dataset = await response.clone().json(); } catch { return response; }
    const result = applyProgramVisibilityPolicy(dataset);
    latestSecondaryPrograms = result.secondaryPrograms;
    queueRender();
    if (result.dataset === dataset) return response;
    const headers = new Headers(response.headers);
    headers.delete("content-length");
    headers.delete("content-encoding");
    headers.set("content-type", "application/json; charset=utf-8");
    return new Response(JSON.stringify(result.dataset), {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  };
  Object.defineProperty(target, "__vivamosProgramVisibilityPolicyInstalled", { value: true });
}

if (typeof window !== "undefined") {
  installStylesheet();
  observeProgramSection();
  installProgramVisibilityPolicy(window);
  if (!shellReady) queueRender();
}
