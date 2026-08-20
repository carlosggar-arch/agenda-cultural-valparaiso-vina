function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function categoryId(event) {
  return String(event?.primary_category?.id || event?.categories?.[0]?.id || "").trim();
}

function dateKey(value) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/);
  return match?.[1] || null;
}

function spanDays(event) {
  const start = dateKey(event?.schedule?.start);
  const end = dateKey(event?.schedule?.end);
  if (!start || !end) return 0;
  const startMs = Date.parse(`${start}T12:00:00Z`);
  const endMs = Date.parse(`${end}T12:00:00Z`);
  return Number.isFinite(startMs) && Number.isFinite(endMs) ? Math.round((endMs - startMs) / 86400000) : 0;
}

export function isLongFormationCycle(event) {
  if (!event || event?.event_type !== "event") return false;
  if (categoryId(event) !== "cursos-talleres") return false;
  if (event?.schedule?.mode !== "multi_day") return false;
  if (Array.isArray(event?.schedule?.occurrences) && event.schedule.occurrences.length) return false;
  if (spanDays(event) < 21) return false;

  const text = fold(`${event?.title || ""} ${event?.description || ""} ${(event?.tags || []).join(" ")}`);
  return /\b(?:ciclo de formacion|ciclo formativo|programa de formacion)\b/.test(text);
}

function asProgram(event) {
  const schedule = { ...(event?.schedule || {}) };
  delete schedule.opening_time;
  delete schedule.closing_time;
  delete schedule.opening_hours;
  delete schedule.hours_confidence;
  delete schedule.recurrence;

  return {
    ...event,
    event_type: "program",
    schedule,
    editorial: {
      ...(event?.editorial || {}),
      classification: "program",
      reason: "long_formation_cycle_not_daily_event",
      original_event_type: event?.event_type || null,
    },
  };
}

export function normalizeFormationCycles(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    if (!isLongFormationCycle(event)) return event;
    changed = true;
    return asProgram(event);
  });
  return changed ? { ...dataset, events } : dataset;
}
