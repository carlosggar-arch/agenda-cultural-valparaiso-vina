import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import {
  groupedScheduleLabel,
  isNonEventDescription,
  normalizePublicTitle,
  publicLocationLabel,
} from "./public-presentation-rules.mjs";

const STYLE_ID = "public-presentation-guard-style";
const CITY_REGISTRY = await loadCityRegistry();
const CITIES = CITY_REGISTRY.byId;

let loadedCity = null;
let loadingCity = null;
let eventsById = new Map();
let queued = false;

function installStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .grouped-exhibition-copy .grouped-exhibition-schedule,
    .grouped-exhibition-copy .grouped-exhibition-location {
      display: block !important;
      margin-top: 3px !important;
      color: #687a74 !important;
      font-size: .82rem !important;
      line-height: 1.3 !important;
    }
    .grouped-exhibition-copy .grouped-exhibition-location::before {
      content: "⌖";
      display: inline-block;
      margin-right: 5px;
      color: #a86731;
      font-weight: 800;
    }
    .availability-badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: .3rem .56rem;
      font-size: .7rem;
      line-height: 1;
      font-weight: 850;
      white-space: nowrap;
      border: 1px solid transparent;
    }
    .availability-badge--sold-out {
      background: #f9e8e5;
      color: #8b3028;
      border-color: #e7b8b0;
    }
    .availability-badge--partial {
      background: #fff1dc;
      color: #7b4e17;
      border-color: #e8c997;
    }
    .availability-badge--last {
      background: #fff4cf;
      color: #75520a;
      border-color: #e6ce75;
    }
    .event-card[data-ticket-availability="sold-out"] {
      border-color: #e3b6af !important;
    }
  `;
  document.head.append(style);
}

function currentCityId() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return CITIES[id] ? id : null;
}

async function ensureEventIndex() {
  const cityId = currentCityId();
  if (!cityId) return;
  if (loadedCity === cityId && eventsById.size) return;
  if (loadingCity === cityId) return;
  loadingCity = cityId;
  try {
    const response = await fetch(CITIES[cityId].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    if (currentCityId() !== cityId || !Array.isArray(dataset?.events)) return;
    eventsById = new Map(dataset.events
      .map((event) => [String(event?.id || "").trim(), event])
      .filter(([id]) => id));
    loadedCity = cityId;
  } catch {
    eventsById = new Map();
  } finally {
    if (loadingCity === cityId) loadingCity = null;
  }
}

function eventIdForNode(node) {
  const grouped = node.closest("[data-grouped-event-id]");
  if (grouped?.dataset.groupedEventId) return grouped.dataset.groupedEventId;
  const card = node.closest(".event-card[data-event-id]");
  if (card?.dataset.eventId) return card.dataset.eventId;
  const detail = node.closest("[data-event-detail]");
  if (detail?.dataset.eventDetail) return detail.dataset.eventDetail;
  return null;
}

function eventForNode(node) {
  const id = String(eventIdForNode(node) || "").trim();
  return id ? eventsById.get(id) || null : null;
}

function cleanTitleNode(node) {
  if (!(node instanceof HTMLElement)) return;
  const event = eventForNode(node);
  if (!event) return;
  const current = String(node.textContent || "").replace(/\s+/g, " ").trim();
  const normalized = normalizePublicTitle(current, event);
  if (!normalized) return;
  // presentation-normalizer.js also observes these nodes. Point its stored source
  // title at the cleaned value so both layers converge instead of undoing each other.
  node.dataset.originalPublicTitle = normalized;
  if (node.textContent !== normalized) node.textContent = normalized;
}

function removePipelineDescription(node) {
  if (!(node instanceof HTMLElement)) return;
  if (isNonEventDescription(node.textContent || "")) node.remove();
}

function ticketAvailability(event) {
  const status = event?.public_status || {};
  const editorial = event?.editorial || {};
  const priceText = String(event?.price?.display_text || "").toLocaleLowerCase("es");
  const stage = String(status.price_stage || "").toLocaleLowerCase("es");

  if (status.sold_out === true) {
    return { key: "sold-out", label: "Entradas agotadas" };
  }
  if (editorial.partial_availability === true || /algunos sectores agotados/.test(priceText)) {
    return { key: "partial", label: "Algunos sectores agotados" };
  }
  if (editorial.last_tickets === true || /últimos tickets|ultimos tickets/.test(`${stage} ${priceText}`)) {
    return { key: "last", label: "Últimos tickets" };
  }
  return null;
}

function enhanceAvailabilityCard(card) {
  if (!(card instanceof HTMLElement)) return;
  const event = eventsById.get(String(card.dataset.eventId || "").trim());
  if (!event) return;

  const state = ticketAvailability(event);
  const existing = card.querySelector("[data-availability-badge]");
  if (!state) {
    existing?.remove();
    delete card.dataset.ticketAvailability;
    return;
  }

  card.dataset.ticketAvailability = state.key;
  const host = card.querySelector(".card-meta-right") || card.querySelector(".card-meta-row");
  if (!(host instanceof HTMLElement)) return;

  const badge = existing || document.createElement("span");
  badge.dataset.availabilityBadge = "";
  badge.className = `availability-badge availability-badge--${state.key}`;
  badge.textContent = state.label;
  badge.setAttribute("aria-label", `Disponibilidad: ${state.label}`);
  if (!existing) host.append(badge);

  if (state.key === "sold-out") {
    for (const chip of card.querySelectorAll(".trust-chip")) {
      if (/inscripci[oó]n abierta/i.test(chip.textContent || "")) chip.remove();
    }
  }
}

function enhanceGroupedRow(row) {
  if (!(row instanceof HTMLElement)) return;
  const event = eventsById.get(String(row.dataset.groupedEventId || "").trim());
  if (!event) return;
  const copy = row.querySelector(".grouped-exhibition-copy");
  if (!(copy instanceof HTMLElement)) return;

  const title = copy.querySelector("strong");
  if (title) cleanTitleNode(title);

  let schedule = copy.querySelector(".grouped-exhibition-schedule");
  if (!schedule) {
    schedule = copy.querySelector("small");
    if (!schedule) {
      schedule = document.createElement("small");
      if (title?.nextSibling) copy.insertBefore(schedule, title.nextSibling);
      else copy.prepend(schedule);
    }
    schedule.classList.add("grouped-exhibition-schedule");
  }
  const city = CITIES[currentCityId()];
  const nextSchedule = groupedScheduleLabel(event, {
    locale: city?.locale || "es-CL",
    timezone: city?.timezone || "America/Santiago",
  });
  if (schedule.textContent !== nextSchedule) schedule.textContent = nextSchedule;

  let location = copy.querySelector(".grouped-exhibition-location");
  if (!location) {
    location = document.createElement("small");
    location.className = "grouped-exhibition-location";
    schedule.insertAdjacentElement("afterend", location);
  }
  const nextLocation = publicLocationLabel(event);
  if (location.textContent !== nextLocation) location.textContent = nextLocation;
}

function applyPresentationRules() {
  document.querySelectorAll([
    '.event-card[data-event-id] .event-card-body h4',
    '.event-card[data-event-id] .card-body h3',
    '.grouped-exhibition-copy strong',
    '.event-detail-title',
  ].join(",")).forEach(cleanTitleNode);

  document.querySelectorAll(".event-card-description").forEach(removePipelineDescription);
  document.querySelectorAll(".event-card[data-event-id]").forEach(enhanceAvailabilityCard);
  document.querySelectorAll("[data-grouped-event-id]").forEach(enhanceGroupedRow);
}

function queueApply() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(async () => {
    queued = false;
    await ensureEventIndex();
    applyPresentationRules();
  });
}

installStyles();
queueApply();

new MutationObserver(queueApply).observe(document.body, {
  childList: true,
  subtree: true,
  characterData: true,
});

new MutationObserver(() => {
  loadedCity = null;
  loadingCity = null;
  eventsById = new Map();
  queueApply();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
