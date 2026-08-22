import { formatSchedule } from "../assets/event-schedule-display.mjs?v=20260821-point8-v2";
import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260821-point8-v2";
import { sessionScheduleLabelForDate, withMissingEventTimeFallback } from "./today-session-presentation.mjs?v=20260821-point8-v2";
import { dailyExhibitionHours, nextDailyExhibitionOpening } from "./date-aware-exhibition-hours.mjs?v=20260822-next-opening1";
import { visibleReferenceDateKey } from "./filter-reference-date.mjs?v=20260821-visible-date1";
import "./exhibition-hours.js?v=20260821-next-hours1";

const DEFAULT_CONFIG = Object.freeze({ locale: "es", timezone: "UTC" });
const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);

let eventIndex = new Map();
let activeConfig = DEFAULT_CONFIG;
let activeCityId = "";
let indexedRevision = 0;
let applyQueued = false;

function syncRuntimeIndex() {
  const requestedCity = String(document.documentElement.dataset.city || "").trim();
  const snapshot = getAgendaRuntimeSnapshot(requestedCity || null);
  if (!snapshot) return false;
  if (activeCityId === snapshot.cityId && indexedRevision === snapshot.revision && eventIndex.size) return true;
  activeCityId = snapshot.cityId;
  activeConfig = snapshot.city || DEFAULT_CONFIG;
  indexedRevision = snapshot.revision;
  eventIndex = new Map(snapshot.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  return true;
}

function stripMediaControls(root = document) {
  root.querySelectorAll(".card-media, .event-card-media, .event-detail-media").forEach((media) => {
    media.querySelectorAll(
      "button, .carousel-control, .carousel-control-next, .carousel-control-prev, .swiper-button-next, .swiper-button-prev, [data-media-nav]",
    ).forEach((control) => control.remove());
    if (media.dataset.mediaOverlayClean !== "true") media.dataset.mediaOverlayClean = "true";
  });
}

function registrationStatusForDisplay(event) {
  const advisory = String(event?.public_status?.advisory_text || "").replace(/\s+/g, " ").trim();
  if (event?.public_status?.sold_out === true || /plazas? agotadas?/i.test(advisory)) return "Plazas agotadas";
  if (event?.public_status?.cancelled === true) return "Inscripción cerrada";
  if (event?.public_status?.registration_open === true) return "Inscripción abierta";
  if (/inscripci[oó]n cerrada|plazo cerrado/i.test(advisory)) return "Inscripción cerrada";
  if (/inscripci[oó]n abierta|plazas? disponibles?/i.test(advisory)) return "Inscripción abierta";
  return "Consulta inscripción y plazas";
}

function isExhibition(event) {
  const primaryId = String(event?.primary_category?.id || "").trim();
  if (EXHIBITION_IDS.has(primaryId)) return true;
  return (event?.categories || []).some((category) => EXHIBITION_IDS.has(String(category?.id || "").trim()));
}

function scheduleWithoutVisitHours(schedule) {
  if (!schedule || typeof schedule !== "object") return schedule;
  const clean = { ...schedule };
  delete clean.opening_time;
  delete clean.closing_time;
  delete clean.opening_hours;
  delete clean.venue_hours;
  delete clean.venue_opening_hours;
  delete clean.visit_hours;
  return clean;
}

function referenceDate() {
  return visibleReferenceDateKey({ timezone: activeConfig.timezone });
}

function formatEventSchedule(schedule, referenceDateKey = null) {
  return formatSchedule(schedule, {
    ...activeConfig,
    referenceDate: referenceDateKey || undefined,
  });
}

function compactReferenceDate(dateKey, locale = activeConfig.locale || "es") {
  const match = String(dateKey || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return String(dateKey || "");
  const [, year, month, day] = match;
  return new Intl.DateTimeFormat(locale, {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), 12)));
}

function visitHoursLabel(daily, nextOpening = null) {
  if (!daily?.label) return null;
  const closed = daily.closed || /^cerrado\b/i.test(daily.label);
  if (!closed) return `Horario de hoy: ${daily.label}`;
  if (!nextOpening?.label || !nextOpening?.referenceDateKey) return "Horario de hoy: Cerrado";
  return `Horario de hoy: Cerrado · Próxima apertura: ${compactReferenceDate(nextOpening.referenceDateKey)} · ${nextOpening.label}`;
}

export function scheduleForEventDisplay(event, options = {}) {
  if (event?.event_type === "registration_period") return registrationStatusForDisplay(event);
  const schedule = event?.schedule;
  if (!schedule) return isExhibition(event) ? "Horario de visita por confirmar" : "Consultar horario en la fuente";

  const visibleDate = options.referenceDate || referenceDate();
  const eventSchedule = scheduleWithoutVisitHours(schedule);
  const datedSessions = sessionScheduleLabelForDate({ ...event, schedule: eventSchedule }, {
    ...activeConfig,
    ...options,
    referenceDate: visibleDate,
  });
  if (datedSessions) return datedSessions;

  if (isExhibition(event)) {
    const hoursOptions = {
      timezone: options.timezone || activeConfig.timezone,
      referenceDate: visibleDate,
    };
    const daily = dailyExhibitionHours(schedule, hoursOptions);
    const nextOpening = daily?.closed ? nextDailyExhibitionOpening(schedule, hoursOptions) : null;
    const range = formatEventSchedule(eventSchedule, visibleDate);
    const hours = visitHoursLabel(daily, nextOpening);
    if (hours) return [range, hours].filter(Boolean).join(" · ");
    return range;
  }

  return withMissingEventTimeFallback(formatEventSchedule(eventSchedule, visibleDate), eventSchedule);
}

function scheduleForDisplay(event) {
  return scheduleForEventDisplay(event);
}

function locationForDisplay(event) {
  const location = { ...(event?.location || {}) };
  const venue = String(location?.venue || "").trim();
  const city = String(location?.city || "").trim();
  if (venue && city && venue.toLocaleLowerCase("es") !== city.toLocaleLowerCase("es")) return `${venue} · ${city}`;
  return venue || city || "Lugar por confirmar";
}

function visibleCopyText(copy) {
  if (!copy) return "";
  const full = String(copy.textContent || "");
  const sr = String(copy.querySelector(".sr-only")?.textContent || "");
  return (sr && full.startsWith(sr) ? full.slice(sr.length) : full).trim();
}

function replaceFactValue(row, value, marker = "scheduleDisplay") {
  const copy = row?.querySelector(":scope > span:last-child");
  if (!copy) return;
  if (visibleCopyText(copy) === value && copy.dataset[marker] === value) return;
  const sr = copy.querySelector(".sr-only");
  copy.replaceChildren();
  if (sr) copy.append(sr);
  copy.append(document.createTextNode(value));
  copy.dataset[marker] = value;
}

function replaceSimpleCardSchedule(card, value) {
  const copy = card.querySelector(":scope > h4 + p");
  if (!copy) return false;
  if (copy.textContent.trim() === value && copy.dataset.scheduleDisplay === value) return true;
  copy.textContent = value;
  copy.dataset.scheduleDisplay = value;
  return true;
}

function replaceSimpleCardLocation(card, value) {
  const schedule = card.querySelector(":scope > h4 + p");
  if (!schedule) return false;

  const copy = card.querySelector(":scope > p[data-location-display]")
    || [...card.querySelectorAll(":scope > p")].find((node) => (
      node !== schedule
      && !node.classList.contains("venue-opening-hours")
      && !node.hasAttribute("data-exhibition-opening-hours")
    ));
  if (!copy) return false;
  if (copy.textContent.trim() === value && copy.dataset.locationDisplay === value) return true;
  copy.textContent = value;
  copy.dataset.locationDisplay = value;
  return true;
}

function enhanceCard(card) {
  const event = eventIndex.get(String(card.dataset.eventId || ""));
  if (!event) return;
  const schedule = scheduleForDisplay(event);
  const location = locationForDisplay(event);
  const facts = [...card.querySelectorAll(".card-fact")];
  const scheduleFact = facts.find((row) => row.querySelector(".sr-only")?.textContent.trim().startsWith("Fecha:"));
  if (scheduleFact) replaceFactValue(scheduleFact, schedule, "scheduleDisplay");
  else replaceSimpleCardSchedule(card, schedule);
  const locationFact = facts.find((row) => row.querySelector(".sr-only")?.textContent.trim().startsWith("Lugar:"));
  if (locationFact) replaceFactValue(locationFact, location, "locationDisplay");
  else replaceSimpleCardLocation(card, location);
}

function enhanceGroupedExhibition(row) {
  const event = eventIndex.get(String(row.dataset.groupedEventId || ""));
  const copy = row.querySelector(".grouped-exhibition-copy > small");
  if (!event || !copy) return;
  const value = scheduleForDisplay(event);
  if (copy.textContent.trim() === value && copy.dataset.scheduleDisplay === value) return;
  copy.textContent = value;
  copy.dataset.scheduleDisplay = value;
}

function replaceDetailFact(dialog, label, value) {
  const fact = [...dialog.querySelectorAll(".event-detail-fact")].find((row) => row.querySelector("strong")?.textContent.trim() === label);
  const copy = fact?.querySelector("span:last-child");
  if (!copy) return;
  if (copy.textContent.trim() === value && copy.dataset.enhancedDisplay === value) return;
  copy.textContent = value;
  copy.dataset.enhancedDisplay = value;
}

function enhanceDetail(dialog) {
  const id = String(dialog.dataset.eventDetail || "");
  const event = eventIndex.get(id);
  if (!event) return;
  replaceDetailFact(dialog, "Fecha y horario", scheduleForDisplay(event));
  replaceDetailFact(dialog, "Lugar", locationForDisplay(event));
}

function apply() {
  applyQueued = false;
  if (!syncRuntimeIndex()) return;
  stripMediaControls();
  document.querySelectorAll(".event-card[data-event-id]").forEach(enhanceCard);
  document.querySelectorAll("[data-grouped-event-id]").forEach(enhanceGroupedExhibition);
  document.querySelectorAll("dialog[data-event-detail]").forEach(enhanceDetail);
}

function queueApply() {
  if (applyQueued) return;
  applyQueued = true;
  queueMicrotask(apply);
}

for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:cards-enriched",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, queueApply);
}
document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-open-event]")) queueMicrotask(queueApply);
  if (target.closest("[data-combined-when] [data-filter-value]")) setTimeout(queueApply, 0);
});
document.addEventListener("change", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.matches("[data-date-from], [data-date-to]")) setTimeout(queueApply, 0);
});
queueApply();
