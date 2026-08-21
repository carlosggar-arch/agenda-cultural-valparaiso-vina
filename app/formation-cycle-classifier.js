function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const TRAINING_CATEGORY_IDS = new Set([
  "formacion",
  "formacion-taller",
  "cursos-talleres",
  "cursos-talleres-campus",
  "talleres-cursos",
  "cursos",
  "talleres",
]);

function categoryId(event) {
  return String(event?.primary_category?.id || event?.categories?.[0]?.id || "").trim();
}

function categoryIds(event) {
  const ids = new Set();
  const primary = String(event?.primary_category?.id || "").trim();
  if (primary) ids.add(primary);
  for (const category of event?.categories || []) {
    const id = String(category?.id || "").trim();
    if (id) ids.add(id);
  }
  return ids;
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

function hasOccurrences(event) {
  return Array.isArray(event?.schedule?.occurrences) && event.schedule.occurrences.length > 0;
}

function formationLike(event) {
  const ids = categoryIds(event);
  if ([...ids].some((id) => TRAINING_CATEGORY_IDS.has(id))) return true;
  const labels = [event?.primary_category?.label, ...(event?.categories || []).map((category) => category?.label)]
    .filter(Boolean)
    .join(" ");
  return /\b(?:formacion|curso|cursos|taller|talleres|campus)\b/.test(fold(labels));
}

function registrationText(event) {
  return fold([
    event?.title,
    event?.description,
    event?.registration_requirements,
    event?.public_status?.advisory_text,
    ...(event?.tags || []),
  ].filter(Boolean).join(" "));
}

function explicitRegistrationProcess(event) {
  const text = registrationText(event);
  return /\b(?:proceso de inscripcion|periodo de inscripcion|plazos? de inscripcion|inscripciones?|inscripcion hasta|matricula|preinscripcion|reserva de plaza|solicitud de plaza)\b/.test(text);
}

function explicitRegistrationSignal(event) {
  if (String(event?.links?.registration || "").trim()) return true;
  if (String(event?.registration_requirements || "").trim()) return true;
  if (event?.public_status?.registration_open === true) return true;
  if (event?.public_status?.sold_out === true && formationLike(event)) return true;
  const text = registrationText(event);
  return /\b(?:inscripciones? abiertas?|inscripcion hasta|matricula|preinscripcion|reserva de plaza|solicitud de plaza|plazas? agotadas?|plazas? disponibles?)\b/.test(text);
}

function longFormationOfferingSignal(event) {
  if (!formationLike(event) || spanDays(event) < 21) return false;
  const title = fold(event?.title);
  return /\b(?:campus|campamento|escuela de verano|programa formativo|programa de formacion)\b/.test(title);
}

export function isRegistrationReminder(event) {
  if (!event || !["event", "program"].includes(event?.event_type)) return false;
  if (event?.schedule?.mode !== "multi_day") return false;
  if (hasOccurrences(event)) return false;
  if (spanDays(event) < 7) return false;

  // Existing programme records are reclassified only when their public copy
  // explicitly says that the item is an enrollment/application process.
  if (event.event_type === "program") return explicitRegistrationProcess(event);

  if (explicitRegistrationProcess(event)) return true;
  if (formationLike(event) && explicitRegistrationSignal(event)) return true;
  return longFormationOfferingSignal(event);
}

function asRegistrationReminder(event) {
  return {
    ...event,
    event_type: "registration_period",
    editorial: {
      ...(event?.editorial || {}),
      classification: "registration_period",
      reason: "enrollment_or_booking_process_not_single_event",
      original_event_type: event?.event_type || null,
    },
  };
}

export function isLongFormationCycle(event) {
  if (!event || event?.event_type !== "event") return false;
  if (!TRAINING_CATEGORY_IDS.has(categoryId(event))) return false;
  if (event?.schedule?.mode !== "multi_day") return false;
  if (hasOccurrences(event)) return false;
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
    if (isRegistrationReminder(event)) {
      changed = true;
      return asRegistrationReminder(event);
    }
    if (!isLongFormationCycle(event)) return event;
    changed = true;
    return asProgram(event);
  });
  return changed ? { ...dataset, events } : dataset;
}
