import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";
import { contentKindPresentation } from "./content-kind-presentation.mjs?v=20260823-contentkind1";

const DAY_ORDER = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"];
const DAY_ALIASES = new Map([
  ["lunes", 0],
  ["martes", 1],
  ["miercoles", 2],
  ["jueves", 3],
  ["viernes", 4],
  ["sabado", 5],
  ["sabados", 5],
  ["domingo", 6],
  ["domingos", 6],
]);
const TIME_RANGE_RE = /(?<!\d)([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)\s*(?:a|hasta|[-–—])\s*([01]?\d|2[0-3])\s*[:.]\s*([0-5]\d)(?!\d)/gi;

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/\s+/g, " ")
    .trim();
}

function safeAbsoluteHttpUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url : null;
  } catch {
    return null;
  }
}

export function browserFriendlySourceUrl(value) {
  return safeAbsoluteHttpUrl(value)?.href || null;
}

export function publicEventSourceUrl(event) {
  const links = event?.links || {};
  const explicitCorroborating = links.presentation_source
    || links.corroborating
    || links.verified_source
    || links.secondary_source;
  return browserFriendlySourceUrl(explicitCorroborating || links.official || links.source || event?.source_url);
}

function dayIndex(value) {
  return DAY_ALIASES.get(fold(value)) ?? -1;
}

function clauseAppliesToDay(clause, weekday) {
  const text = fold(clause);
  const target = dayIndex(weekday);
  if (target < 0) return false;

  const range = text.match(/\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\s+a\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s?\b/);
  if (range) {
    const start = dayIndex(range[1]);
    const end = dayIndex(range[2]);
    if (start >= 0 && end >= start && target >= start && target <= end) return true;
  }

  const targetName = DAY_ORDER[target];
  return new RegExp(`\\b${targetName}s?\\b`).test(text);
}

function clock(hour, minute) {
  return `${String(Number(hour)).padStart(2, "0")}:${minute}`;
}

function scheduleClauses(displayText) {
  return String(displayText || "")
    .split(/;|\.(?=\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])/)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function openingHoursForWeekday(displayText, weekday) {
  const source = String(displayText || "").trim();
  if (!source || dayIndex(weekday) < 0) return null;

  for (const clause of scheduleClauses(source)) {
    if (!clauseAppliesToDay(clause, weekday)) continue;
    const ranges = [];
    for (const match of clause.matchAll(TIME_RANGE_RE)) {
      ranges.push(`${clock(match[1], match[2])}–${clock(match[3], match[4])}`);
    }
    if (ranges.length) return ranges.join(" y ");
  }
  return null;
}

function dateKey(value) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/);
  return match?.[1] || null;
}

function localDateKey(date, timezone) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function localWeekday(date, timezone, locale = "es") {
  return new Intl.DateTimeFormat(locale || "es", {
    timeZone: timezone,
    weekday: "long",
  }).format(date);
}

export function currentVisitHours(event, { now = new Date(), timezone = "UTC", locale = "es" } = {}) {
  const opening = event?.schedule?.venue_hours || event?.schedule?.opening_hours;
  if (!opening) return null;

  const today = localDateKey(now, timezone);
  const start = dateKey(event?.schedule?.start);
  const end = dateKey(event?.schedule?.end || event?.schedule?.start);
  if (start && today < start) return null;
  if (end && today > end) return null;

  const explicitToday = String(opening.today_display_text || "").trim();
  if (explicitToday) return explicitToday;
  return openingHoursForWeekday(opening.display_text, localWeekday(now, timezone, locale));
}

export function applyContentKindBadge(card, event, city) {
  if (!card || !event) return false;
  const meta = card.querySelector(".card-meta-row");
  if (!meta) return false;

  const presentation = contentKindPresentation(event, city);
  card.dataset.contentKind = presentation.kind;
  let badge = meta.querySelector(".content-kind-badge");
  let changed = false;
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "type-badge content-kind-badge";
    meta.append(badge);
    changed = true;
  }
  if (badge.textContent !== presentation.label) {
    badge.textContent = presentation.label;
    changed = true;
  }
  if (badge.dataset.contentKind !== presentation.kind) {
    badge.dataset.contentKind = presentation.kind;
    changed = true;
  }
  if (badge.title !== presentation.detail) {
    badge.title = presentation.detail;
    changed = true;
  }
  badge.setAttribute("aria-label", `${presentation.label}: ${presentation.detail}`);
  return changed;
}

export function enhanceBaseEventCard(card, event, city, now = new Date()) {
  if (!card || !event) return false;
  let changed = applyContentKindBadge(card, event, city);

  // Point 8 is the schedule authority. Canonical schedules are rendered by the
  // shared schedule-display layer; this legacy quality pass must not append
  // venue hours to the event-time line and recreate mixed clocks.
  if (!event?.schedule?.schedule_contract_version) {
    const hours = currentVisitHours(event, {
      now,
      timezone: city?.timezone || "UTC",
      locale: city?.locale || "es",
    });
    if (hours) {
      const directParagraphs = [...card.children].filter((node) => node.tagName === "P");
      const schedule = directParagraphs[0];
      if (schedule && !card.querySelector(":scope > .venue-opening-hours")) {
        const visit = document.createElement("p");
        visit.className = "venue-opening-hours";
        visit.dataset.visitHoursApplied = "true";
        visit.textContent = `Horario de visita: ${hours}`;
        schedule.insertAdjacentElement("afterend", visit);
        changed = true;
      }
    }
  }

  const source = publicEventSourceUrl(event);
  const link = card.querySelector(".event-bottom a");
  if (source && link && link.href !== source) {
    link.href = source;
    link.dataset.sourceQualityPolicy = "browser-friendly";
    changed = true;
  }
  return changed;
}

function representativeEventForCard(card, byId) {
  const directId = String(card?.dataset?.eventId || "").trim();
  if (directId) return byId.get(directId) || null;
  const groupedIds = String(card?.dataset?.eventGroup || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  for (const id of groupedIds) {
    const event = byId.get(id);
    if (event) return event;
  }
  return null;
}

function applyCardDataQualityPolicy() {
  const cityId = String(document.documentElement.dataset.city || "").trim();
  const snapshot = getAgendaRuntimeSnapshot(cityId);
  if (!snapshot?.events?.length) return 0;
  const byId = new Map(snapshot.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  let changed = 0;
  const now = new Date();
  for (const card of document.querySelectorAll(".event-card[data-event-id], .event-card[data-event-group]")) {
    const event = representativeEventForCard(card, byId);
    if (!event) continue;
    const cardChanged = card.dataset.eventId
      ? enhanceBaseEventCard(card, event, snapshot.city, now)
      : applyContentKindBadge(card, event, snapshot.city);
    if (cardChanged) changed += 1;
  }
  return changed;
}

let queued = false;
function scheduleApply() {
  if (queued) return;
  queued = true;
  queueMicrotask(() => {
    queued = false;
    applyCardDataQualityPolicy();
  });
}

if (typeof document !== "undefined" && typeof window !== "undefined") {
  for (const eventName of [
    "vivamos:agenda-data-ready",
    "vivamos:agenda-rendered",
    "vivamos:cards-enriched",
  ]) {
    window.addEventListener(eventName, scheduleApply);
  }
  scheduleApply();
}
