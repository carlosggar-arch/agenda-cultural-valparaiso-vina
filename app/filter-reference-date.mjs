import { dateKeyForTimezone } from "./date-aware-exhibition-hours.mjs?v=20260821-date-hours1";

function addDays(dateKey, days) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(dateKey || ""))) return null;
  const date = new Date(`${dateKey}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function weekdayForKey(dateKey) {
  return new Date(`${dateKey}T12:00:00Z`).getUTCDay();
}

function weekendStart(todayKey) {
  const weekday = weekdayForKey(todayKey);
  const daysToFriday = weekday === 5 ? 0 : weekday === 6 ? -1 : weekday === 0 ? -2 : 5 - weekday;
  return addDays(todayKey, daysToFriday);
}

export function visibleReferenceDateKey({ root = document, timezone = "UTC", now = new Date() } = {}) {
  const today = dateKeyForTimezone(now, timezone);
  if (!today) return null;

  const active = root.querySelector(
    '[data-combined-when] [data-filter-value].active, [data-combined-when] [data-filter-value][aria-pressed="true"]',
  );
  const when = String(active?.dataset?.filterValue || "todos");

  if (when === "manana") return addDays(today, 1);
  if (when === "fin-de-semana") {
    const start = weekendStart(today);
    if (!start) return today;
    const end = addDays(start, 2);
    return start <= today && today <= end ? today : start;
  }
  if (when === "personalizado") {
    const from = String(root.querySelector("[data-date-from]")?.value || "").trim();
    const to = String(root.querySelector("[data-date-to]")?.value || "").trim();
    return from || to || today;
  }
  return today;
}

export { addDays };
