const PUBLIC_EVENT_SERIES_RULES = Object.freeze([
  Object.freeze({
    id: "bioparc-candlelight-repertoires-2026",
    cityId: "gijon",
    match: Object.freeze({
      officialUrl: "https://acuariogijon.es/actividad/concierto-piano-a-la-luz-de-las-velas/",
    }),
    sessions: Object.freeze([
      Object.freeze({ key: "bandas-sonoras", title: "Piano a la luz de las velas — Grandes bandas sonoras", start: "2026-08-29T19:00:00" }),
      Object.freeze({ key: "tributo-pop", title: "Piano a la luz de las velas — Tributo a ABBA, Queen, The Beatles y Mecano", start: "2026-08-29T20:30:00" }),
      Object.freeze({ key: "canciones-inolvidables", title: "Piano a la luz de las velas — Canciones inolvidables", start: "2026-08-30T19:30:00" }),
    ]),
    authority: "official_session_program",
  }),
]);

function cleanUrl(value) {
  return String(value || "").trim().replace(/\/$/, "");
}

function localStart(value) {
  return String(value || "").replace(/(?:Z|[+-]\d{2}:\d{2})$/, "");
}

function eventOfficialUrl(event) {
  return cleanUrl(event?.links?.official || event?.links?.source || event?.source_url);
}

function matchesRule(event, rule, cityId) {
  if (rule?.cityId && String(rule.cityId) !== String(cityId || "")) return false;
  if (rule?.match?.eventId && String(event?.id || "") !== String(rule.match.eventId)) return false;
  if (rule?.match?.sourceId && String(event?.source_id || "") !== String(rule.match.sourceId)) return false;
  if (rule?.match?.officialUrl && eventOfficialUrl(event) !== cleanUrl(rule.match.officialUrl)) return false;
  return true;
}

function eventOccurrences(event) {
  const occurrences = Array.isArray(event?.schedule?.occurrences) ? event.schedule.occurrences : [];
  return occurrences.filter((occurrence) => occurrence?.start);
}

function occurrenceForSession(occurrences, session) {
  return occurrences.find((occurrence) => localStart(occurrence.start) === localStart(session.start));
}

function displayText(start, end) {
  const day = String(start).slice(0, 10);
  const begin = String(start).match(/T(\d{2}:\d{2})/)?.[1];
  const finish = String(end || "").startsWith(`${day}T`) ? String(end).match(/T(\d{2}:\d{2})/)?.[1] : null;
  return [day, begin && finish && finish !== begin ? `${begin}–${finish}` : begin].filter(Boolean).join(" · ");
}

function expandEvent(event, rule) {
  const occurrences = eventOccurrences(event);
  const resolved = (rule.sessions || []).map((session) => ({
    session,
    occurrence: occurrenceForSession(occurrences, session),
  }));

  // Fail closed: never remove a programme shell unless every declared child
  // maps one-to-one to source-backed occurrence evidence.
  if (!resolved.length || resolved.some(({ occurrence }) => !occurrence)) return null;
  if (new Set(resolved.map(({ occurrence }) => localStart(occurrence.start))).size !== resolved.length) return null;

  return resolved.map(({ session, occurrence }) => {
    const end = occurrence.end || occurrence.start;
    return {
      ...event,
      id: `${event.id}__${session.key}`,
      title: session.title,
      description: session.description || session.title,
      schedule: {
        ...(event.schedule || {}),
        mode: "dated",
        start: occurrence.start,
        end,
        display_text: displayText(occurrence.start, end),
        occurrences: [{ ...occurrence, end }],
      },
      editorial: {
        ...(event.editorial || {}),
        classification: "event",
        reason: "official_program_expanded_to_sessions",
        event_family_id: event.id,
        event_family_rule: rule.id,
        session_key: session.key,
        session_authority: rule.authority || "declared_session_program",
        parent_event_id: event.id,
      },
    };
  });
}

function recalculateCounts(events, original = {}) {
  return {
    ...original,
    total: events.length,
    events: events.filter((event) => !["program", "flexible_offer", "course"].includes(event?.event_type)).length,
    courses: events.filter((event) => event?.event_type === "course").length,
    flexible_offers: events.filter((event) => event?.event_type === "flexible_offer").length,
    programs: events.filter((event) => event?.event_type === "program").length,
  };
}

export function normalizeEventSeries(dataset, {
  cityId = "",
  rules = PUBLIC_EVENT_SERIES_RULES,
} = {}) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = [];
  for (const event of dataset.events) {
    const rule = rules.find((candidate) => matchesRule(event, candidate, cityId));
    const expanded = rule ? expandEvent(event, rule) : null;
    if (!expanded) events.push(event);
    else {
      events.push(...expanded);
      changed = true;
    }
  }
  return changed ? { ...dataset, events, counts: recalculateCounts(events, dataset.counts) } : dataset;
}

export { PUBLIC_EVENT_SERIES_RULES };
