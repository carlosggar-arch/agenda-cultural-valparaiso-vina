const CINEMA_CATEGORY = "cine";
const PAJAREANDO_PATTERN = /curso\s+para\s+profes\s+pajareando\s+aprendo/i;
const CLOCK_LIST = /\b(?:[01]\d|2[0-3]):[0-5]\d\b/g;

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function isTimedStart(value) {
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(String(value || ""));
}

function datePart(value) {
  return String(value || "").match(/^(\d{4}-\d{2}-\d{2})/)?.[1] || null;
}

function timePart(value) {
  return String(value || "").match(/T(\d{2}:\d{2})/)?.[1] || null;
}

function offsetPart(value) {
  return String(value || "").match(/(Z|[+-]\d{2}:\d{2})$/)?.[1] || "-04:00";
}

function localIso(day, clock, template) {
  return `${day}T${clock}:00${offsetPart(template)}`;
}

function minutes(clock) {
  const match = String(clock || "").match(/^(\d{2}):(\d{2})$/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

function isCinema(event) {
  if (event?.event_type !== "event") return false;
  if (event?.primary_category?.id === CINEMA_CATEGORY) return true;
  return (event?.categories || []).some((category) => category?.id === CINEMA_CATEGORY);
}

function locationKey(event) {
  const venueId = String(event?.location?.venue_id || "").trim();
  if (venueId) return venueId;
  return fold([event?.location?.venue, event?.location?.city].filter(Boolean).join(" "));
}

function sourceKey(event) {
  return String(event?.source_id || "").trim() || fold(event?.source_name || event?.organizer);
}

function priceKey(event) {
  const price = event?.price || {};
  return [
    price.is_free === true ? "free" : price.is_free === false ? "paid" : "unknown",
    String(price.currency || ""),
    String(price.min_amount ?? ""),
    String(price.max_amount ?? ""),
    fold(price.display_text),
  ].join("|");
}

function bookingKey(event) {
  const links = event?.links || {};
  const candidate = links.tickets || links.registration || links.official || links.source || event?.source_url;
  if (!candidate) return "";
  try {
    const url = new URL(String(candidate));
    return `${url.hostname.toLocaleLowerCase("en")}${url.pathname.replace(/\/$/, "")}`;
  } catch {
    return fold(candidate);
  }
}

export function cinemaSessionGroupKey(event) {
  if (!isCinema(event) || !isTimedStart(event?.schedule?.start)) return null;
  const title = fold(event?.title);
  const source = sourceKey(event);
  const location = locationKey(event);
  if (!(title && source && location)) return null;
  return [source, location, title, priceKey(event), bookingKey(event)].join("||");
}

function eventOccurrences(event) {
  const structured = Array.isArray(event?.schedule?.occurrences) ? event.schedule.occurrences : [];
  const candidates = structured.length
    ? structured
    : event?.schedule?.start
      ? [{ start: event.schedule.start, end: event.schedule.end || event.schedule.start }]
      : [];
  return candidates
    .filter((occurrence) => isTimedStart(occurrence?.start))
    .map((occurrence) => ({ start: occurrence.start, end: occurrence.end || occurrence.start }));
}

function uniqueSortedOccurrences(events) {
  const unique = new Map();
  for (const event of events) {
    for (const occurrence of eventOccurrences(event)) {
      const key = `${occurrence.start}|${occurrence.end || ""}`;
      if (!unique.has(key)) unique.set(key, occurrence);
    }
  }
  return [...unique.values()].sort((a, b) => String(a.start).localeCompare(String(b.start)) || String(a.end).localeCompare(String(b.end)));
}

function occurrenceDisplayText(occurrences) {
  const groups = new Map();
  for (const occurrence of occurrences) {
    const day = datePart(occurrence.start);
    const start = timePart(occurrence.start);
    if (!(day && start)) continue;
    const endDay = datePart(occurrence.end);
    const end = endDay === day ? timePart(occurrence.end) : null;
    const clock = end && end !== start ? `${start}–${end}` : start;
    const times = groups.get(day) || [];
    if (!times.includes(clock)) times.push(clock);
    groups.set(day, times);
  }
  return [...groups.entries()].map(([day, times]) => `${day} · ${times.join(", ")}`).join(" · ");
}

function mergeCinemaGroup(events) {
  const occurrences = uniqueSortedOccurrences(events);
  if (events.length < 2 || occurrences.length < 2) return events[0];
  const ordered = [...events].sort((a, b) => String(a?.schedule?.start || "").localeCompare(String(b?.schedule?.start || "")));
  const base = ordered[0];
  const first = occurrences[0];
  const last = occurrences[occurrences.length - 1];
  return {
    ...base,
    schedule: {
      ...(base.schedule || {}),
      mode: "multi_session",
      start: first.start,
      end: last.end || last.start,
      display_text: occurrenceDisplayText(occurrences),
      occurrences,
    },
    editorial: {
      ...(base.editorial || {}),
      session_grouping: "same_title_source_venue_price",
      merged_session_ids: ordered.map((event) => event.id).filter(Boolean),
      merged_session_count: occurrences.length,
    },
  };
}

export function mergeRepeatedCinemaSessions(events) {
  if (!Array.isArray(events) || events.length < 2) return events;
  const groups = new Map();
  events.forEach((event, index) => {
    const key = cinemaSessionGroupKey(event);
    if (!key) return;
    const group = groups.get(key) || [];
    group.push({ event, index });
    groups.set(key, group);
  });

  const replacements = new Map();
  const removed = new Set();
  for (const group of groups.values()) {
    if (group.length < 2) continue;
    const merged = mergeCinemaGroup(group.map(({ event }) => event));
    const firstIndex = Math.min(...group.map(({ index }) => index));
    replacements.set(firstIndex, merged);
    for (const { index } of group) if (index !== firstIndex) removed.add(index);
  }
  if (!replacements.size) return events;

  const output = [];
  events.forEach((event, index) => {
    if (removed.has(index)) return;
    output.push(replacements.get(index) || event);
  });
  return output;
}

function isPajareandoEvent(event) {
  if (!PAJAREANDO_PATTERN.test(String(event?.title || ""))) return false;
  const source = String(event?.source_url || event?.links?.official || event?.links?.source || "").toLocaleLowerCase("es");
  const venue = fold(event?.location?.venue);
  return source.includes("artequinvina.cl") || venue.includes("artequin");
}

export function recoverPajareandoOccurrences(event) {
  if (!isPajareandoEvent(event)) return event;
  const schedule = event?.schedule || {};
  if (Array.isArray(schedule.occurrences) && schedule.occurrences.length >= 2) return event;
  const startDay = datePart(schedule.start);
  const endDay = datePart(schedule.end);
  const clocks = String(schedule.display_text || "").match(CLOCK_LIST) || [];
  if (!(startDay && endDay && startDay !== endDay && clocks.length === 4)) return event;
  if (timePart(schedule.start) && timePart(schedule.start) !== clocks[0]) return event;
  const values = clocks.map(minutes);
  if (values.some((value) => value === null) || values[0] >= values[1] || values[2] >= values[3]) return event;

  const occurrences = [
    { start: localIso(startDay, clocks[0], schedule.start), end: localIso(startDay, clocks[1], schedule.start) },
    { start: localIso(endDay, clocks[2], schedule.start), end: localIso(endDay, clocks[3], schedule.start) },
  ];
  return {
    ...event,
    title: "Pajareando Aprendo — curso para profes",
    schedule: {
      ...schedule,
      mode: "multi_session",
      start: occurrences[0].start,
      end: occurrences[1].end,
      display_text: occurrenceDisplayText(occurrences),
      occurrences,
    },
    editorial: {
      ...(event.editorial || {}),
      session_grouping: "artequin_pajareando_source_schedule",
      recovered_session_count: 2,
    },
  };
}

function isGenericVenueTitle(event) {
  const title = fold(event?.title);
  const venue = fold(event?.location?.venue);
  return Boolean(title && venue && title === venue);
}

function freePrice(price = {}) {
  return { ...price, is_free: true, currency: "CLP", min_amount: 0, max_amount: 0, display_text: "Gratis" };
}

export function correctKnownExhibitions(event) {
  const title = fold(event?.title);
  const description = String(event?.description || "");
  const source = String(event?.source_url || event?.links?.official || event?.links?.source || "").toLocaleLowerCase("es");
  const venue = fold(event?.location?.venue);

  if ((isGenericVenueTitle(event) || title.includes("galeria municipal de arte")) && /PRÁCTICAS\s+SITUADAS/i.test(description)) {
    return {
      ...event,
      title: "Prácticas situadas — 46.º Salón de Estudiantes",
      primary_category: { id: "exposiciones", label: "Exposiciones" },
      categories: [{ id: "exposiciones", label: "Exposiciones" }],
      schedule: {
        ...(event.schedule || {}),
        opening_time: null,
        closing_time: null,
        opening_hours: {
          display_text: "Lunes a viernes · 10:00–18:00 · Sábados · 11:00–17:00",
          opening_time: "10:00",
          closing_time: "18:00",
        },
      },
      editorial: { ...(event.editorial || {}), title_recovery: "description_headline", schedule_correction: "venue_opening_hours" },
    };
  }

  if ((source.includes("museobaburizza.cl") || venue.includes("baburizza")) && title === "nebulosa carina") {
    return {
      ...event,
      title: "Nebulosa Carina",
      schedule: {
        ...(event.schedule || {}),
        mode: "multi_day",
        start: "2026-08-06",
        end: "2026-10-04",
        display_text: "2026-08-06 – 2026-10-04",
        occurrences: [],
        opening_time: null,
        closing_time: null,
        opening_hours: null,
      },
      price: freePrice(event.price),
      editorial: { ...(event.editorial || {}), schedule_correction: "official_baburizza_virtual_exhibition" },
    };
  }

  if ((source.includes("museobaburizza.cl") || venue.includes("baburizza")) && title === "las cumbias que escuchamos alla arriba") {
    return {
      ...event,
      title: "Las cumbias que escuchamos allá arriba",
      schedule: {
        ...(event.schedule || {}),
        mode: "multi_day",
        start: "2026-08-14",
        end: "2026-10-04",
        display_text: "2026-08-14 – 2026-10-04",
        occurrences: [],
        opening_time: "10:00",
        closing_time: "18:00",
        recurrence: ["Martes a domingo"],
        hours_confidence: "official_event_page",
      },
      price: freePrice(event.price),
      editorial: { ...(event.editorial || {}), schedule_correction: "official_baburizza_exhibition" },
    };
  }

  return event;
}

function recalculateCounts(events, originalCounts = {}) {
  const counts = { ...originalCounts };
  counts.total = events.length;
  counts.events = events.filter((event) => !["program", "flexible_offer", "course"].includes(event?.event_type)).length;
  counts.courses = events.filter((event) => event?.event_type === "course").length;
  counts.flexible_offers = events.filter((event) => event?.event_type === "flexible_offer").length;
  counts.programs = events.filter((event) => event?.event_type === "program").length;
  return counts;
}

export function normalizeSessionOccurrences(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const recovered = dataset.events.map(correctKnownExhibitions).map(recoverPajareandoOccurrences);
  const merged = mergeRepeatedCinemaSessions(recovered);
  const changed = merged.length !== dataset.events.length || merged.some((event, index) => event !== dataset.events[index]);
  if (!changed) return dataset;
  return { ...dataset, events: merged, counts: recalculateCounts(merged, dataset.counts) };
}
