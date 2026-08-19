const PROGRAM_TYPE = "program";
const MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre";
let pendingPrograms = [];

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function key(value) {
  return clean(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_(?:valparaiso|vina_del_mar)$/g, "");
}

function coverageKeys(events) {
  const keys = new Set();
  for (const event of events || []) {
    if (event?.event_type === PROGRAM_TYPE) continue;
    for (const value of [event?.source_id, event?.location?.venue_id, event?.organizer, event?.location?.venue]) {
      const normalized = key(value);
      if (normalized) keys.add(normalized);
    }
  }
  return keys;
}

export function isProgramCovered(program, concreteEvents) {
  const covered = Array.isArray(program?.editorial?.covered_source_ids)
    ? program.editorial.covered_source_ids.map(key).filter(Boolean)
    : [];
  if (!covered.length) return false;
  const available = coverageKeys(concreteEvents);
  return covered.every((item) => available.has(item));
}

export function partitionPrograms(events) {
  const list = Array.isArray(events) ? events : [];
  const publicEvents = list.filter((event) => event?.event_type !== PROGRAM_TYPE);
  const programs = list.filter((event) => event?.event_type === PROGRAM_TYPE);
  const secondaryPrograms = programs.filter((program) => !isProgramCovered(program, publicEvents));
  const hiddenPrograms = programs.filter((program) => !secondaryPrograms.includes(program));
  return { publicEvents, secondaryPrograms, hiddenPrograms };
}

function countsFor(events, original = {}) {
  return {
    ...original,
    total: events.length,
    events: events.filter((event) => !["program", "flexible_offer", "course"].includes(event?.event_type)).length,
    programs: 0,
  };
}

export function applyWebProgramPolicy(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return { dataset, secondaryPrograms: [], hiddenPrograms: [] };
  const { publicEvents, secondaryPrograms, hiddenPrograms } = partitionPrograms(dataset.events);
  if (!secondaryPrograms.length && !hiddenPrograms.length) return { dataset, secondaryPrograms, hiddenPrograms };
  return {
    dataset: { ...dataset, events: publicEvents, counts: countsFor(publicEvents, dataset.counts) },
    secondaryPrograms,
    hiddenPrograms,
  };
}

export function programReferenceTitle(program) {
  const original = clean(program?.title) || "Programación general";
  const month = original.match(new RegExp(`\\b(${MONTHS})\\b`, "i"))?.[1]?.toLocaleLowerCase("es");
  const subject = clean(program?.organizer || program?.location?.venue || program?.source_name || "Programación");
  return month ? `${subject} — programación de ${month}` : original;
}

function programLink(program) {
  const value = program?.links?.official || program?.links?.source || program?.source_url;
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function renderPrograms() {
  document.querySelector("[data-web-program-references]")?.remove();
  if (!pendingPrograms.length) return;
  const main = document.querySelector("main");
  if (!main) return;
  const section = document.createElement("section");
  section.className = "shell web-program-references";
  section.dataset.webProgramReferences = "true";
  const details = document.createElement("details");
  details.className = "web-program-details";
  const summary = document.createElement("summary");
  summary.textContent = `Carteleras y programaciones (${pendingPrograms.length})`;
  const copy = document.createElement("p");
  copy.className = "web-program-intro";
  copy.textContent = "Referencias generales que conservamos solo cuando todavía quedan actividades por desglosar con suficiente fiabilidad.";
  const grid = document.createElement("div");
  grid.className = "web-program-grid";
  for (const program of pendingPrograms) {
    const card = document.createElement("article");
    card.className = "web-program-card";
    const title = document.createElement("h3");
    title.textContent = programReferenceTitle(program);
    const source = document.createElement("p");
    source.textContent = `Fuente: ${clean(program?.source_name || program?.organizer || "referencia oficial")}`;
    card.append(title, source);
    const href = programLink(program);
    if (href) {
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Ver programación completa →";
      card.append(link);
    }
    grid.append(card);
  }
  details.append(summary, copy, grid);
  section.append(details);
  main.append(section);
}

function installStyles() {
  if (document.querySelector("style[data-web-program-policy]")) return;
  const style = document.createElement("style");
  style.dataset.webProgramPolicy = "true";
  style.textContent = `
    .web-program-references{margin-top:2rem;margin-bottom:3rem}
    .web-program-details{border:1px solid rgba(8,43,89,.14);border-radius:18px;background:#fff;padding:1rem 1.2rem}
    .web-program-details>summary{cursor:pointer;font-weight:800;color:#0b4d42;font-size:1.05rem}
    .web-program-intro{margin:.8rem 0 1rem;color:#5c6f6a}
    .web-program-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.9rem}
    .web-program-card{border:1px solid rgba(8,43,89,.1);border-radius:14px;padding:1rem;background:#fbfcfb}
    .web-program-card h3{margin:0 0 .45rem;font-size:1rem}
    .web-program-card p{margin:0 0 .75rem;color:#62716d}
    .web-program-card a{font-weight:700;color:#0b5b50;text-decoration:none}
  `;
  document.head.append(style);
}

function isAgendaRequest(input, response) {
  const urls = [response?.url, typeof input === "string" ? input : input?.url].filter(Boolean);
  return urls.some((value) => /(?:^|\/)agenda_web\.json(?:[?#]|$)/.test(String(value)));
}

export function installWebProgramPolicy(target = globalThis) {
  if (!target || typeof target.fetch !== "function" || target.__vivamosWebProgramPolicyInstalled) return;
  const upstreamFetch = target.fetch.bind(target);
  target.fetch = async (...args) => {
    const response = await upstreamFetch(...args);
    if (!response?.ok || !isAgendaRequest(args[0], response)) return response;
    let dataset;
    try { dataset = await response.clone().json(); } catch { return response; }
    const result = applyWebProgramPolicy(dataset);
    pendingPrograms = result.secondaryPrograms;
    queueMicrotask(renderPrograms);
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
  Object.defineProperty(target, "__vivamosWebProgramPolicyInstalled", { value: true });
}

if (typeof window !== "undefined") {
  installStyles();
  installWebProgramPolicy(window);
}
