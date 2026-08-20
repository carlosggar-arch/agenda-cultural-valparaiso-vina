import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import "./startup-stability.js?v=20260819-startup2";
import "./render-lifecycle.js?v=20260819-lifecycle1";

// The core is intentionally a dynamic import: the watchdog above must execute
// even if the core module graph fails to load or evaluate.
const { coreReady } = await import("./app-core.js?v=20260820-recovery1");

// Content presentation is shared across cities. City-specific modules are data
// adapters or media enrichers only; they do not own exhibition-card structure.
const IMAGE_QUALITY_GUARD = "./image-quality-guard.js?v=20260820-images3";
const OPTIONAL_MODULES = [
  "./temporal-priority.js?v=20260819-temporal3",
  "./exhibition-groups.js?v=20260820-groups1",
  "./multievent-layout-fix.js?v=20260820-multievent2",
  "./schedule-display.js?v=20260819-runtime1",
  "./footer-credit.js?v=20260818-footer3",
  "./community-source.js?v=20260818-feedback3",
  "./participation-footer.js?v=20260819-feedback7",
];

// Only genuinely city-specific behavior is deferred for Gijón. Exhibition
// grouping, subcards, scrolling and schedule presentation use the same modules
// as Valparaíso/Viña and every future city.
const GIJON_DEFERRED_MODULES = new Set([
  "./temporal-priority.js?v=20260819-temporal3",
]);
const IS_GIJON = String(document.documentElement.dataset.city || "") === "gijon";
if (IS_GIJON) {
  for (let index = OPTIONAL_MODULES.length - 1; index >= 0; index -= 1) {
    if (GIJON_DEFERRED_MODULES.has(OPTIONAL_MODULES[index])) OPTIONAL_MODULES.splice(index, 1);
  }
  OPTIONAL_MODULES.push("./gijon-card-images.js?v=20260820-images2");
  document.documentElement.dataset.gijonStableRuntime = "true";
} else {
  // These enrichers are currently Valpo/Viña specific, but the exhibition
  // renderer itself above is common and consumes the shared runtime snapshot.
  OPTIONAL_MODULES.push(
    "./card-experience.js?v=20260819-runtime1",
    "./card-image-fallback.js?v=20260819-runtime1",
    "./public-presentation-guard.js?v=20260820-text1",
    "./exhibition-hours.js?v=20260820-hours5",
  );
}

function ensureSourcesFallbackLink() {
  const footer = document.querySelector("body > footer");
  if (!footer) return null;
  const dynamic = footer.querySelector("[data-sources-toggle]");
  if (dynamic) return dynamic;

  let fallback = footer.querySelector("[data-sources-fallback]");
  if (!fallback) {
    fallback = document.createElement("a");
    fallback.href = "../fuentes.html";
    fallback.className = "sources-toggle sources-fallback";
    fallback.dataset.sourcesFallback = "";
    fallback.textContent = "Fuentes";
    fallback.setAttribute("aria-label", "Ver todas las fuentes de la agenda");
    const version = footer.querySelector("[data-app-version]");
    if (version) footer.insertBefore(fallback, version);
    else footer.append(fallback);
  }
  footer.classList.add("vivamos-footer--with-sources");
  return fallback;
}

function placeSourcesButtonInFooter() {
  const footer = document.querySelector("body > footer");
  const button = footer?.querySelector("[data-sources-toggle]");
  if (!footer || !button) return false;

  footer.querySelector("[data-sources-fallback]")?.remove();
  const version = footer.querySelector("[data-app-version]");
  if (version && button.nextElementSibling !== version) footer.insertBefore(button, version);
  footer.classList.add("vivamos-footer--with-sources");

  const styleId = "vivamos-footer-sources-layout";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .vivamos-footer.vivamos-footer--with-sources {
        grid-template-columns: auto minmax(0, 1fr) auto auto auto;
      }
      .vivamos-footer .sources-toggle {
        display:inline-flex;
        align-items:center;
        justify-content:center;
        min-height:2.35rem;
        padding:.5rem .85rem;
        border:1px solid rgba(255,255,255,.72);
        border-radius:999px;
        background:#fff;
        color:#174f46;
        font:inherit;
        font-weight:850;
        line-height:1;
        text-decoration:none;
        cursor:pointer;
      }
      .vivamos-footer .sources-toggle:hover,
      .vivamos-footer .sources-toggle:focus-visible {
        border-color:#f4d16d;
        background:#f4d16d;
        color:#103c36;
        outline:2px solid rgba(255,255,255,.72);
        outline-offset:2px;
      }
      @media (max-width: 900px) {
        .vivamos-footer.vivamos-footer--with-sources {
          grid-template-columns: 1fr auto;
        }
        .vivamos-footer.vivamos-footer--with-sources .sources-toggle {
          grid-column: 1;
          width: max-content;
        }
      }
    `;
    document.head.append(style);
  }
  return true;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loadImageQualityGuard() {
  if (IS_GIJON) return;
  const delays = [0, 250, 1000];
  let lastError = null;
  for (const delay of delays) {
    if (delay) await wait(delay);
    try {
      await import(IMAGE_QUALITY_GUARD);
      document.documentElement.dataset.imageQualityGuard = "ready";
      return;
    } catch (error) {
      lastError = error;
    }
  }
  document.documentElement.dataset.imageQualityGuard = "failed";
  console.warn("¡Vivamos!: no se pudo cargar la protección de imágenes tras varios intentos", lastError);
}

async function loadOptionalEnhancements() {
  if (!IS_GIJON) void loadImageQualityGuard();

  const results = await Promise.allSettled(OPTIONAL_MODULES.map((module) => import(module)));
  results.forEach((result, index) => {
    if (result.status === "rejected") console.warn(`¡Vivamos!: mejora opcional omitida (${OPTIONAL_MODULES[index]})`, result.reason);
  });

  // The public source catalogue must always be reachable. Install a normal
  // link first; if the richer in-page source toggle loads successfully, it
  // replaces this fallback. This avoids losing Fuentes because of an optional
  // module failure, missing source section, cache mismatch or footer timing.
  ensureSourcesFallbackLink();
  try {
    await import("./sources-toggle.js?v=20260820-sources2");
  } catch (error) {
    console.warn("¡Vivamos!: vista integrada de fuentes omitida; se conserva el enlace de catálogo", error);
  }
  if (!placeSourcesButtonInFooter()) ensureSourcesFallbackLink();
}

await coreReady;
void loadOptionalEnhancements();

let exhibitionOrderQueued = false;

function defaultFiltersAreNeutral() {
  const when = document.querySelector('[data-combined-when] [data-filter-value].active')?.dataset?.filterValue || "todos";
  const area = document.querySelector('[data-combined-area] [data-filter-value].active')?.dataset?.filterValue || "todos";
  const categories = document.querySelectorAll('[data-combined-category-filters] [data-combined-category].active').length;
  const query = String(document.querySelector('[data-smart-search]')?.value || "").trim();
  const from = String(document.querySelector('[data-date-from]')?.value || "").trim();
  const to = String(document.querySelector('[data-date-to]')?.value || "").trim();
  return when === "todos" && area === "todos" && categories === 0 && !query && !from && !to;
}

function placeExhibitionsLast() {
  exhibitionOrderQueued = false;
  if (!defaultFiltersAreNeutral()) return;
  const grid = document.querySelector('[data-dated-grid]');
  if (!grid) return;
  const cards = [...grid.children].filter((node) => node.classList?.contains("event-card"));
  if (cards.length < 2) return;
  const regular = cards.filter((card) => card.dataset.category !== "exposiciones");
  const exhibitions = cards.filter((card) => card.dataset.category === "exposiciones");
  if (!regular.length || !exhibitions.length) return;
  const ordered = [...regular, ...exhibitions];
  if (ordered.every((card, index) => card === cards[index])) return;
  const fragment = document.createDocumentFragment();
  for (const card of ordered) fragment.append(card);
  grid.append(fragment);
}

function scheduleExhibitionOrder() {
  if (exhibitionOrderQueued) return;
  exhibitionOrderQueued = true;
  queueMicrotask(placeExhibitionsLast);
}

// Ordering is presentation policy too, so it is now shared rather than tied to
// one city. The observer only watches direct children and cannot loop on text or images.
const datedGrid = document.querySelector('[data-dated-grid]');
if (datedGrid) {
  new MutationObserver(scheduleExhibitionOrder).observe(datedGrid, { childList: true });
}
document.addEventListener("click", (event) => {
  if (event.target.closest('[data-filter-value], [data-combined-category], [data-filter-clear]')) scheduleExhibitionOrder();
});
document.addEventListener("input", (event) => {
  if (event.target.matches('[data-smart-search], [data-date-from], [data-date-to]')) scheduleExhibitionOrder();
});
scheduleExhibitionOrder();

// ---------------------------------------------------------------------------
// Registration reminders
// ---------------------------------------------------------------------------
// Enrollment, booking and application windows are useful agenda information,
// but they are not cultural events. The data pipeline marks them with the
// shared `registration_period` type; this presentation boundary then keeps
// them in their own common section for every city.
const REGISTRATION_TYPE = "registration_period";
const REGISTRATION_STYLE_ID = "vivamos-registration-reminders";
let registrationSyncTimer = null;
let registrationMutationObserver = null;

function currentRuntimeSnapshot() {
  const cityId = String(document.documentElement.dataset.city || "").trim();
  return cityId ? getAgendaRuntimeSnapshot(cityId) : null;
}

function registrationStatus(event) {
  const advisory = String(event?.public_status?.advisory_text || "").replace(/\s+/g, " ").trim();
  if (event?.public_status?.sold_out === true || /plazas? agotadas?/i.test(advisory)) return "Plazas agotadas";
  if (event?.public_status?.cancelled === true) return "Inscripción cerrada";
  if (event?.public_status?.registration_open === true) return "Inscripción abierta";
  if (/inscripci[oó]n cerrada|plazo cerrado/i.test(advisory)) return "Inscripción cerrada";
  if (/inscripci[oó]n abierta|plazas? disponibles?/i.test(advisory)) return "Inscripción abierta";
  return "Consulta inscripción y plazas";
}

function installRegistrationStyles() {
  if (document.getElementById(REGISTRATION_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = REGISTRATION_STYLE_ID;
  style.textContent = `
    .registration-reminders-section .registration-reminder-badge {
      white-space: nowrap;
    }
    .registration-reminders-section .event-card--registration > h4 + [data-registration-status],
    .registration-reminders-section .event-card--registration h4 + [data-registration-status] {
      font-weight: 750;
    }
    .registration-reminders-section .event-card--registration[data-registration-closed="true"] [data-registration-status] {
      font-weight: 800;
    }
  `;
  document.head.append(style);
}

function ensureRegistrationSection() {
  const agenda = document.querySelector("[data-agenda]");
  if (!agenda) return null;
  let section = agenda.querySelector("[data-registration-section]");
  if (section) return section;

  section = document.createElement("section");
  section.className = "content-section secondary-section registration-reminders-section";
  section.dataset.registrationSection = "";
  section.hidden = true;
  section.innerHTML = `
    <div class="section-heading">
      <div>
        <p class="eyebrow">Para apuntarte a tiempo</p>
        <h3>Inscripciones y plazos</h3>
        <p>Procesos de inscripción, matrícula, reserva de plaza y convocatorias. Son recordatorios, no eventos de la agenda fechada.</p>
      </div>
      <span class="section-count"><strong data-registration-total>0</strong> recordatorios</span>
    </div>
    <div class="event-grid compact-grid" data-registration-grid></div>`;

  const programSection = agenda.querySelector("[data-program-section]");
  if (programSection) agenda.insertBefore(section, programSection);
  else {
    const flexibleSection = agenda.querySelector("[data-flexible-section]");
    if (flexibleSection) agenda.insertBefore(section, flexibleSection);
    else agenda.append(section);
  }
  installRegistrationStyles();
  return section;
}

function visibleActivityCount(grid) {
  if (!grid) return 0;
  let count = 0;
  for (const card of grid.querySelectorAll(":scope > .event-card")) {
    if (card.hidden) continue;
    if (!card.dataset.eventGroup) {
      count += 1;
      continue;
    }
    const rows = [...card.querySelectorAll(".grouped-exhibition-item")];
    if (rows.length) count += rows.filter((row) => !row.hidden).length;
    else count += String(card.dataset.eventGroup || "").split(",").filter(Boolean).length;
  }
  return count;
}

function patchRegistrationCard(card, event) {
  if (!card || !event) return;
  card.classList.remove("event-card--dated");
  card.classList.add("event-card--registration");
  card.dataset.registrationReminder = "true";
  const status = registrationStatus(event);
  card.dataset.registrationClosed = /agotadas|cerrada/i.test(status) ? "true" : "false";

  const meta = card.querySelector(".card-meta-row");
  if (meta) {
    let badge = meta.querySelector("[data-registration-badge]");
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "type-badge registration-reminder-badge";
      badge.dataset.registrationBadge = "";
      meta.append(badge);
    }
    badge.textContent = "Inscripción";
  }

  const schedule = card.querySelector(":scope > h4 + p") || card.querySelector("h4 + p");
  if (schedule) {
    schedule.dataset.registrationStatus = "";
    schedule.textContent = status;
  }
}

function updateRegistrationTotals(section) {
  if (!section) return;
  const registrationGrid = section.querySelector("[data-registration-grid]");
  const registration = visibleActivityCount(registrationGrid);
  const dated = visibleActivityCount(document.querySelector("[data-dated-grid]"));
  const program = visibleActivityCount(document.querySelector("[data-program-grid]"));
  const flexible = visibleActivityCount(document.querySelector("[data-flexible-grid]"));
  const total = dated + registration + program + flexible;

  const setCount = (selector, value) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = String(value);
  };
  setCount("[data-registration-total]", registration);
  setCount("[data-dated-total]", dated);
  setCount("[data-program-total]", program);
  setCount("[data-flexible-total]", flexible);
  setCount("[data-total]", total);
  section.hidden = registration === 0;

  const empty = document.querySelector("[data-empty]");
  if (empty && total > 0) empty.hidden = true;

  const summary = document.querySelector("[data-filter-summary]");
  if (summary?.textContent) {
    summary.textContent = summary.textContent.replace(
      /^\d+\s+actividades?/,
      `${total} ${total === 1 ? "actividad" : "actividades"}`,
    );
  }
}

function syncRegistrationReminders() {
  registrationSyncTimer = null;
  const snapshot = currentRuntimeSnapshot();
  const section = ensureRegistrationSection();
  if (!section || !snapshot) {
    if (section) section.hidden = true;
    return;
  }

  const registrationGrid = section.querySelector("[data-registration-grid]");
  const events = snapshot.events.filter((event) => event?.event_type === REGISTRATION_TYPE);
  const byId = new Map(events.map((event) => [String(event?.id || "").trim(), event]).filter(([id]) => id));

  for (const card of [...registrationGrid.querySelectorAll(":scope > .event-card[data-event-id]")]) {
    if (!byId.has(String(card.dataset.eventId || ""))) card.remove();
  }

  for (const [id, event] of byId) {
    const escaped = globalThis.CSS?.escape ? CSS.escape(id) : id.replace(/["\\]/g, "\\$&");
    const candidates = [...document.querySelectorAll(`.event-card[data-event-id="${escaped}"]`)];
    const outside = candidates.find((card) => card.parentElement !== registrationGrid);
    const existing = candidates.find((card) => card.parentElement === registrationGrid);
    if (outside && existing && outside !== existing) existing.remove();
    const card = outside || existing;
    if (!card) continue;
    patchRegistrationCard(card, event);
    if (card.parentElement !== registrationGrid) registrationGrid.append(card);
  }

  if (!registrationMutationObserver) {
    registrationMutationObserver = new MutationObserver(() => scheduleRegistrationSync(20));
    registrationMutationObserver.observe(registrationGrid, {
      subtree: true,
      attributes: true,
      attributeFilter: ["hidden"],
    });
  }

  updateRegistrationTotals(section);
}

function scheduleRegistrationSync(delay = 0) {
  if (registrationSyncTimer) clearTimeout(registrationSyncTimer);
  registrationSyncTimer = setTimeout(syncRegistrationReminders, delay);
}

if (datedGrid) {
  new MutationObserver(() => scheduleRegistrationSync(20)).observe(datedGrid, { childList: true });
}
for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:cards-enriched",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, () => scheduleRegistrationSync(30));
}
new MutationObserver(() => {
  if (registrationMutationObserver) {
    registrationMutationObserver.disconnect();
    registrationMutationObserver = null;
  }
  scheduleRegistrationSync(80);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-filter-value], [data-combined-category], [data-filter-clear], [data-section-filter], [data-category-filter]')) {
    scheduleRegistrationSync(60);
  }
});
document.addEventListener("input", (event) => {
  if (event.target.matches('[data-smart-search], [data-search], [data-date-from], [data-date-to]')) scheduleRegistrationSync(60);
});
window.addEventListener("pageshow", () => scheduleRegistrationSync(80), { passive: true });
scheduleRegistrationSync(0);
