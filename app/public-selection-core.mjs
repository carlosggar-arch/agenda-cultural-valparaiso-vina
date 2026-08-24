import {
  addDays,
  dateKeyForDate,
  eventDateRanges,
  weekendBounds,
} from "./temporal-priority-core.mjs?v=20260821-temporal4";
import { canonicalPublicCategory } from "./public-category-rules.mjs?v=20260821-shared-taxonomy1";
import { compareAgendaOrder, diversifySortedAgendaEvents } from "./agenda-order-core.mjs?v=20260823-editorial1";
import { eventLifecycle } from "./runtime-past-event-guard.mjs?v=20260823-pastguard5";

const ALL_SECTIONS = new Set(["todos", "all"]);
const TODAY_SECTIONS = new Set(["hoy", "today"]);
const TOMORROW_SECTIONS = new Set(["manana", "mañana", "tomorrow"]);
const WEEKEND_SECTIONS = new Set(["fin-de-semana", "this_weekend"]);
const SEVEN_DAY_SECTIONS = new Set(["7-dias", "siete-dias", "next_7_days"]);
const UPCOMING_SECTIONS = new Set(["proximos", "upcoming"]);
const ENDING_SOON_SECTIONS = new Set(["terminan-pronto", "ending_soon"]);

function overlap(range, start, end) {
  return Boolean(range?.start && range?.end && range.start <= end && range.end >= start);
}

export function canonicalCategoryId(event) {
  return canonicalPublicCategory(event)?.id || "otros";
}

export function eventMatchesCanonicalSection(event, sectionId, city, now = new Date(), custom = {}) {
  const section = String(sectionId || "").trim();
  if (ALL_SECTIONS.has(section)) return true;
  if (section === "gratis") return event?.price?.is_free === true;
  if (["talleres-cursos", "cursos-talleres"].includes(section)) {
    return ["course", "workshop"].includes(String(event?.event_type || ""))
      || canonicalCategoryId(event) === "talleres-cursos";
  }
  if (section === "programas") return event?.event_type === "program";

  const today = dateKeyForDate(now, city);
  const ranges = eventDateRanges(event, city);
  if (!today || !ranges.length) return false;
  if (TODAY_SECTIONS.has(section)) return ranges.some((range) => overlap(range, today, today));
  if (TOMORROW_SECTIONS.has(section)) {
    const tomorrow = addDays(today, 1);
    return ranges.some((range) => overlap(range, tomorrow, tomorrow));
  }
  if (WEEKEND_SECTIONS.has(section)) {
    const weekend = weekendBounds(today);
    return ranges.some((range) => overlap(range, weekend.start, weekend.end));
  }
  if (SEVEN_DAY_SECTIONS.has(section)) return ranges.some((range) => overlap(range, today, addDays(today, 6)));
  if (ENDING_SOON_SECTIONS.has(section)) {
    const end = addDays(today, Number(custom.endingSoonDays ?? 3));
    return ranges.some((range) => range.start <= today && range.end > today && range.end <= end);
  }
  if (UPCOMING_SECTIONS.has(section)) return ranges.some((range) => range.end >= today);
  if (section === "personalizado") {
    const start = custom.from || custom.to;
    const end = custom.to || custom.from;
    if (!start || !end) return false;
    const low = start <= end ? start : end;
    const high = start <= end ? end : start;
    return ranges.some((range) => overlap(range, low, high));
  }
  return false;
}

export function canonicalEventIds(events, sectionId, city, now = new Date(), custom = {}) {
  return (events || []).filter((event) => eventMatchesCanonicalSection(event, sectionId, city, now, custom))
    .map((event) => String(event?.id || "")).filter(Boolean).sort();
}

export function canonicalSelectionSnapshot(events, sectionId, city, now = new Date(), custom = {}) {
  const selected = (events || [])
    .filter((event) => eventMatchesCanonicalSection(event, sectionId, city, now, custom))
    .sort((left, right) => compareAgendaOrder(left, right, city, now));
  const ordered = diversifySortedAgendaEvents(selected, city, now);
  return ordered.map((event, index) => {
    const lifecycle = eventLifecycle(event, { now, timeZone: city?.timezone || event?.schedule?.timezone || "UTC" });
    return Object.freeze({
      position: index,
      id: String(event?.id || ""),
      sectionId: String(sectionId || ""),
      categoryId: canonicalCategoryId(event),
      lifecycleState: lifecycle.state,
      visible: lifecycle.visible !== false,
    });
  }).filter((record) => record.id);
}
