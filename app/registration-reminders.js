import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";

const REGISTRATION_TYPE = "registration_period";
const STYLE_ID = "vivamos-registration-reminders";
let syncTimer = null;
let registrationObserver = null;

function currentRuntimeSnapshot() {
  const cityId = String(document.documentElement.dataset.city || "").trim();
  return cityId ? getAgendaRuntimeSnapshot(cityId) : null;
}

export function registrationStatus(event) {
  const advisory = String(event?.public_status?.advisory_text || "").replace(/\s+/g, " ").trim();
  if (event?.public_status?.sold_out === true || /plazas? agotadas?/i.test(advisory)) return "Plazas agotadas";
  if (event?.public_status?.cancelled === true) return "Inscripción cerrada";
  if (event?.public_status?.registration_open === true) return "Inscripción abierta";
  if (/inscripci[oó]n cerrada|plazo cerrado/i.test(advisory)) return "Inscripción cerrada";
  if (/inscripci[oó]n abierta|plazas? disponibles?/i.test(advisory)) return "Inscripción abierta";
  return "Consulta inscripción y plazas";
}

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
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

function ensureSection() {
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
  installStyles();
  return section;
}

function visibleItemCount(grid) {
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

function patchCard(card, event) {
  if (!card || !event) return;
  card.classList.remove("event-card--dated", "event-card--program");
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

function updateTotals(section) {
  if (!section) return;
  const registration = visibleItemCount(section.querySelector("[data-registration-grid]"));
  const dated = visibleItemCount(document.querySelector("[data-dated-grid]"));
  const program = visibleItemCount(document.querySelector("[data-program-grid]"));
  const flexible = visibleItemCount(document.querySelector("[data-flexible-grid]"));

  // Registration reminders are useful public items, but they are deliberately
  // excluded from the cultural-activity total because they are not events.
  const activityTotal = dated + program + flexible;
  const setCount = (selector, value) => {
    const node = document.querySelector(selector);
    if (node) node.textContent = String(value);
  };
  setCount("[data-registration-total]", registration);
  setCount("[data-dated-total]", dated);
  setCount("[data-program-total]", program);
  setCount("[data-flexible-total]", flexible);
  setCount("[data-total]", activityTotal);
  section.hidden = registration === 0;

  const empty = document.querySelector("[data-empty]");
  if (empty && (activityTotal > 0 || registration > 0)) empty.hidden = true;

  const summary = document.querySelector("[data-filter-summary]");
  if (summary?.textContent) {
    summary.textContent = summary.textContent.replace(
      /^\d+\s+actividades?/,
      `${activityTotal} ${activityTotal === 1 ? "actividad" : "actividades"}`,
    );
  }
}

export function syncRegistrationReminders() {
  syncTimer = null;
  const snapshot = currentRuntimeSnapshot();
  const section = ensureSection();
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
    patchCard(card, event);
    if (card.parentElement !== registrationGrid) registrationGrid.append(card);
  }

  if (!registrationObserver) {
    registrationObserver = new MutationObserver(() => scheduleSync(20));
    registrationObserver.observe(registrationGrid, {
      subtree: true,
      attributes: true,
      attributeFilter: ["hidden"],
    });
  }

  updateTotals(section);
}

function scheduleSync(delay = 0) {
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(syncRegistrationReminders, delay);
}

const datedGrid = document.querySelector("[data-dated-grid]");
if (datedGrid) new MutationObserver(() => scheduleSync(20)).observe(datedGrid, { childList: true });

for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:cards-enriched",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, () => scheduleSync(30));
}

new MutationObserver(() => {
  if (registrationObserver) {
    registrationObserver.disconnect();
    registrationObserver = null;
  }
  scheduleSync(80);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

document.addEventListener("click", (event) => {
  if (event.target instanceof Element && event.target.closest(
    "[data-filter-value], [data-combined-category], [data-filter-clear], [data-section-filter], [data-category-filter]",
  )) scheduleSync(60);
});

document.addEventListener("input", (event) => {
  if (event.target instanceof Element && event.target.matches(
    "[data-smart-search], [data-search], [data-date-from], [data-date-to]",
  )) scheduleSync(60);
});

window.addEventListener("pageshow", () => scheduleSync(80), { passive: true });
syncRegistrationReminders();
