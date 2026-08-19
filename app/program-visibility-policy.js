const PROGRAM_TYPE = "program";
const MONTHS = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre";

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

export function isGenericProgramListing(event) {
  if (!event || typeof event !== "object" || event?.event_type === PROGRAM_TYPE) return false;
  if (event?.image?.relevance !== "generic_schedule") return false;

  const title = fold(event?.title);
  const description = fold(event?.description);
  const mentions = (String(event?.description || "").match(/@[a-z0-9_.]+/gi) || []).length;

  if (/\b(cartelera|programacion|agenda|calendario)\b/.test(title)) return true;
  if (new RegExp(`^(?:destino|panoramas?) .+ (?:${MONTHS}) 20\\d{2}$`).test(title)) return true;
  return /\beste mes (?:tenemos|incluye|trae|hay)\b/.test(description) && mentions >= 2;
}

function normalizeProgramLikeEvent(event) {
  if (event?.event_type === PROGRAM_TYPE || !isGenericProgramListing(event)) return event;
  return {
    ...event,
    event_type: PROGRAM_TYPE,
    editorial: {
      ...(event?.editorial || {}),
      classification: PROGRAM_TYPE,
      reason: "generic_schedule_not_individual_event",
      original_event_type: event?.event_type || null,
    },
  };
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
  const list = (Array.isArray(events) ? events : []).map(normalizeProgramLikeEvent);
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

export function ensureProgramVisibilityStyles() {
  if (typeof document === "undefined" || document.querySelector('link[data-program-visibility-policy]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./program-visibility-policy.css?v=20260819-programs3";
  link.dataset.programVisibilityPolicy = "true";
  document.head.append(link);
}

export function renderProgramReferences({ section, grid, total }, programs = []) {
  if (!(section && grid)) return;
  ensureProgramVisibilityStyles();

  const list = Array.isArray(programs) ? programs : [];
  const heading = section.querySelector(".section-heading");
  const eyebrow = heading?.querySelector(".eyebrow");
  const title = heading?.querySelector("h3");
  const copy = heading?.querySelector("p:not(.eyebrow)");
  const countLabel = total?.parentElement;

  if (eyebrow) eyebrow.textContent = "Referencia complementaria";
  if (title) title.textContent = "Carteleras y programaciones";
  if (copy) copy.textContent = "Solo aparecen aquí cuando todavía no hemos podido desglosar toda la cartelera en eventos individuales fiables.";
  if (countLabel && total && countLabel.dataset.programCountLabel !== "true") {
    countLabel.replaceChildren(total, document.createTextNode(" carteleras"));
    countLabel.dataset.programCountLabel = "true";
  }

  if (!list.length) {
    grid.replaceChildren();
    if (total) total.textContent = "0";
    section.hidden = true;
    return;
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

  grid.replaceChildren(...list.map(programCard));
  if (total) total.textContent = String(list.length);
  const summary = details.querySelector("summary");
  if (summary) summary.textContent = `Ver ${list.length} ${list.length === 1 ? "cartelera de referencia" : "carteleras de referencia"}`;
  section.hidden = false;
}
