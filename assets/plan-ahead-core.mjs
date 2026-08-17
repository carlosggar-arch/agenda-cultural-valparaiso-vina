const DAY_MS = 24 * 60 * 60 * 1000;

export const PLAN_AHEAD_DEFAULTS = Object.freeze({
  minDays: 14,
  maxDays: 56,
  limit: 6,
});

function text(value) {
  return String(value ?? "").trim();
}

function safeUrl(value) {
  const candidate = text(value);
  return /^https?:\/\//i.test(candidate) ? candidate : null;
}

function parseMoment(value) {
  const candidate = text(value);
  if (!candidate) return null;
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(candidate);
  const parsed = new Date(dateOnly ? `${candidate}T12:00:00` : candidate);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function eventPlanningMoment(event) {
  const schedule = event?.schedule || {};
  const direct = parseMoment(schedule.start);
  if (direct) return direct;
  for (const occurrence of schedule.occurrences || []) {
    const parsed = parseMoment(occurrence?.start);
    if (parsed) return parsed;
  }
  return null;
}

export function planAheadAction(event) {
  const links = event?.links || {};
  const status = event?.public_status || {};
  const tickets = safeUrl(links.tickets);
  const registration = safeUrl(links.registration);
  const reservation = safeUrl(links.reservation || links.booking);
  const official = safeUrl(links.official) || safeUrl(event?.source_url) || safeUrl(links.source);
  const requirements = text(event?.registration_requirements);

  if (registration && status.registration_closed !== true) {
    return { kind: "registration", label: "Inscripción abierta", actionLabel: "Inscribirme", url: registration };
  }
  if (status.registration_open === true && official && status.registration_closed !== true) {
    return { kind: "registration", label: "Inscripción abierta", actionLabel: "Ver inscripción", url: official };
  }
  if (reservation && status.reservation_closed !== true) {
    return { kind: "reservation", label: "Reserva disponible", actionLabel: "Reservar", url: reservation };
  }
  if (status.reservation_open === true && official && status.reservation_closed !== true) {
    return { kind: "reservation", label: "Reserva disponible", actionLabel: "Ver reserva", url: official };
  }
  if (tickets && status.sold_out !== true) {
    return { kind: "tickets", label: "Entradas disponibles", actionLabel: "Comprar entradas", url: tickets };
  }
  if (requirements && official && status.registration_closed !== true) {
    return { kind: "requirements", label: "Requiere inscripción", actionLabel: "Ver requisitos", url: official };
  }
  return null;
}

function limitedCapacity(event) {
  const haystack = [
    event?.registration_requirements,
    event?.description,
    ...(event?.tags || []),
    event?.public_status?.advisory_text,
  ].map(text).join(" ").toLocaleLowerCase("es");
  return /\b(cupos? limitad[oa]s?|plazas? limitad[oa]s?|aforo limitad[oa]?|hasta agotar (?:cupos|plazas)|aforo reducido)\b/.test(haystack);
}

function registrationDeadline(event) {
  return parseMoment(
    event?.registration_deadline
    || event?.public_status?.registration_deadline
    || event?.registration?.deadline,
  );
}

function actionPriority(kind) {
  if (kind === "registration") return 4;
  if (kind === "reservation") return 3;
  if (kind === "requirements") return 2;
  if (kind === "tickets") return 1;
  return 0;
}

export function planAheadCandidate(event, options = {}) {
  const now = options.now instanceof Date ? options.now : new Date(options.now || Date.now());
  const minDays = Number.isFinite(options.minDays) ? options.minDays : PLAN_AHEAD_DEFAULTS.minDays;
  const maxDays = Number.isFinite(options.maxDays) ? options.maxDays : PLAN_AHEAD_DEFAULTS.maxDays;
  const type = text(event?.event_type || "event");
  const status = event?.public_status || {};

  if (!event?.id || !["event", "course"].includes(type)) return null;
  if (status.cancelled === true || status.sold_out === true) return null;

  const startsAt = eventPlanningMoment(event);
  if (!startsAt) return null;
  const daysUntil = Math.ceil((startsAt.getTime() - now.getTime()) / DAY_MS);
  if (daysUntil < minDays || daysUntil > maxDays) return null;

  const action = planAheadAction(event);
  if (!action) return null;

  const limited = limitedCapacity(event);
  const deadline = registrationDeadline(event);
  const badges = [action.label];
  if (limited) badges.push("Cupos limitados");

  return {
    event,
    startsAt,
    daysUntil,
    action,
    badges,
    limited,
    deadline,
    score: (limited ? 40 : 0) + actionPriority(action.kind) * 10 - daysUntil / 100,
  };
}

export function selectPlanAhead(events, options = {}) {
  const limit = Number.isFinite(options.limit) ? options.limit : PLAN_AHEAD_DEFAULTS.limit;
  return (events || [])
    .map((event) => planAheadCandidate(event, options))
    .filter(Boolean)
    .sort((left, right) => right.score - left.score || left.startsAt - right.startsAt || String(left.event.title || "").localeCompare(String(right.event.title || ""), "es"))
    .slice(0, limit);
}

export function referenceNow(payload) {
  return parseMoment(payload?.generated_at) || new Date();
}
