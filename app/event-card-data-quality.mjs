import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-shared-runtime1";

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
  // Do not split on the decimal dot inside clocks such as 9.30. A sentence dot
  // only acts as a separator when the next non-space character is a letter.
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
  const opening = event?.schedule?.opening_hours;
  if (!opening) return null;

  const today = localDateKey(now, timezone);
  const start = dateKey(event?.schedule?.start);
  const end = dateKey(event?.schedule?.end || event?.schedule?.start);

  // Weekly venue hours are useful on the card only while the dated exhibition
  // is actually running. This prevents today's venue schedule leaking into a
  // future or already-finished exhibition.
  if (start && today < start) return null;
  if (end && today > end) return null;

  const explicitToday = String(opening.today_display_text || "").trim();
  if (explicitToday) return explicitToday;

  return openingHoursForWeekday(opening.display_text, localWeekday(now, timezone, locale));
}

export function enhanceBaseEventCard(card, event, city, now = new Date()) {
  if (!card || !event) return false;
  let changed = false;

  const hours = currentVisitHours(event, {
    now,
    timezone: city?.timezone || "UTC",
    locale: city?.locale || "es",
  });
  if (hours) {
    const directParagraphs = [...card.children].filter((node) => node.tagName === "P");
    const schedule = directParagraphs[0];
    if (schedule && !schedule.dataset.visitHoursApplied) {
      schedule.textContent = `${schedule.textContent.trim()} · hoy ${hours}`;
      schedule.dataset.visitHoursApplied = "true";
      changed = true;
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

function applyCardDataQualityPolicy() {
  const cityId = String(document.documentElement.dataset.city || "").trim();
  const snapshot = getAgendaRuntimeSnapshot(cityId);
  if (!snapshot?.events?.length) return 0;
  const byId = new Map(snapshot.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  let changed = 0;
  const now = new Date();
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    const event = byId.get(String(card.dataset.eventId || ""));
    if (event && enhanceBaseEventCard(card, event, snapshot.city, now)) changed += 1;
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
