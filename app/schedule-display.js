import { formatSchedule } from "../assets/event-schedule-display.mjs?v=20260819-hours3";
import { gijonLocationForEvent, scheduleForGijonEvent } from "./gijon-venue-hours.js";
import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { todaySessionScheduleLabel } from "./today-session-presentation.mjs?v=20260820-today1";
import { dailyExhibitionHours } from "./date-aware-exhibition-hours.mjs?v=20260821-date-hours1";

const FALLBACK_CONFIG = Object.freeze({
  valparaiso: { id: "valparaiso", locale: "es-CL", timezone: "America/Santiago" },
  gijon: { id: "gijon", locale: "es-ES", timezone: "Europe/Madrid" },
});
const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);

let eventIndex = new Map();
let activeConfig = FALLBACK_CONFIG.valparaiso;
let activeCityId = "valparaiso";
let indexedRevision = 0;
let applyQueued = false;

function currentCity() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return FALLBACK_CONFIG[id] ? id : "valparaiso";
}

function syncRuntimeIndex() {
  const city = currentCity();
  const snapshot = getAgendaRuntimeSnapshot(city);
  if (!snapshot) return false;
  if (activeCityId === city && indexedRevision === snapshot.revision && eventIndex.size) return true;
  activeCityId = city;
  activeConfig = snapshot.city || FALLBACK_CONFIG[city] || FALLBACK_CONFIG.valparaiso;
  indexedRevision = snapshot.revision;
  eventIndex = new Map(snapshot.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
  return true;
}

function safeHttpUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(String(value), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
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
  delete clean.venue_opening_hours;
  delete clean.visit_hours;
  return clean;
}

function scheduleForDisplay(event) {
  if (event?.event_type === "registration_period") return registrationStatusForDisplay(event);
  const schedule = activeCityId === "gijon" ? scheduleForGijonEvent(event) : event?.schedule;
  if (!schedule) return "Horario por confirmar";

  // A multi-session event that happens today must show only today's sessions.
  // This rule is structural: it uses structured occurrences when available and
  // can also recover explicit dated function/session lists from source copy.
  const todaySessions = todaySessionScheduleLabel({ ...event, schedule }, activeConfig);
  if (todaySessions) return todaySessions;

  if (isExhibition(event)) {
    const daily = dailyExhibitionHours(schedule, {
      timezone: activeConfig.timezone,
      now: new Date(),
    });
    const range = formatSchedule(scheduleWithoutVisitHours(schedule), activeConfig);
    if (daily?.label) return [range, daily.label].filter(Boolean).join(" · ");
    // If the source only provides a weekly/seasonal free-text schedule, keep the
    // exhibition dates but omit those generic hours rather than showing hours
    // that may belong to another day.
    return range;
  }

  return formatSchedule(schedule, activeConfig);
}

function locationForDisplay(event) {
  const location = activeCityId === "gijon" ? gijonLocationForEvent(event) : { ...(event?.location || {}) };
  const venue = String(location?.venue || "").trim();
  const city = String(location?.city || "").trim();
  const foldedVenue = venue
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es");
  if (activeCityId === "gijon" && ["gijon/xixon", "gijon", "xixon"].includes(foldedVenue)) return "Lugar por confirmar";
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
  const copy = schedule?.nextElementSibling;
  if (!copy || copy.tagName !== "P") return false;
  if (copy.textContent.trim() === value && copy.dataset.locationDisplay === value) return true;
  copy.textContent = value;
  copy.dataset.locationDisplay = value;
  return true;
}

function enhanceSource(card, event) {
  if (activeCityId !== "gijon" || event?.source_id !== "gijon_opendata_events") return;
  const official = safeHttpUrl(event?.links?.official || event?.links?.source);
  if (!official) return;
  const link = card.querySelector(".event-card-source-link");
  if (!link) return;
  const label = "Ayuntamiento de Gijón/Xixón · ficha oficial ↗";
  if (link.href !== official) link.href = official;
  if (link.textContent !== label) link.textContent = label;
  const prefix = card.querySelector(".event-card-source-prefix");
  if (prefix && prefix.textContent !== "Fuente oficial: ") prefix.textContent = "Fuente oficial: ";
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
  enhanceSource(card, event);
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
  if (activeCityId === "gijon" && event?.source_id === "gijon_opendata_events") {
    replaceDetailFact(dialog, "Fuente", "Ayuntamiento de Gijón/Xixón · Agenda de Eventos");
  }
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
  if (event.target instanceof Element && event.target.closest("[data-open-event]")) queueMicrotask(queueApply);
});
queueApply();
