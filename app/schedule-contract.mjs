const CLOCK_PATTERN = /\b([01]?\d|2[0-3])[:.]([0-5]\d)\b/g;
const CLAUSE_SPLIT_PATTERN = /[·;|\n]+/;
const RANGE_SEPARATOR_PATTERN = /^\s*[-–—]\s*$/;
const ROLE_MARKER_PATTERN = /(?<venue>horarios?\s+(?:(?:del?|de\s+la|de\s+los|de\s+las)\s+)?(?:museo|recinto|sala|galer[ií]a|centro|visita)|horario\s+de\s+visita|horas?\s+de\s+visita)|(?<doors>apertura\s+de\s+puertas|puertas|acceso|ingreso)|(?<session>funci[oó]n(?:es)?|sesi[oó]n(?:es)?|pases?|proyecci[oó]n(?:es)?|concierto|recital|obra|espect[aá]culo|show|charla|taller|actividad|evento)/giu;
const START_CUE_PATTERN = /(?:a\s+las?|comienza|inicio|desde)\s*$/iu;
const EXHIBITION_IDS = new Set(["exposiciones", "museos"]);

function validClock(value) {
  const match = String(value || "").trim().match(/^([01]?\d|2[0-3])[:.]([0-5]\d)$/);
  return match ? `${String(Number(match[1])).padStart(2, "0")}:${match[2]}` : null;
}

function unique(values) {
  return [...new Set(values.map(validClock).filter(Boolean))];
}

function naturalTimeList(values) {
  const times = unique(values);
  if (!times.length) return null;
  if (times.length === 1) return times[0];
  if (times.length === 2) return `${times[0]} y ${times[1]}`;
  return `${times.slice(0, -1).join(", ")} y ${times.at(-1)}`;
}

function timePart(value) {
  return String(value || "").match(/T(\d{2}:\d{2})/)?.[1] || null;
}

function datePart(value) {
  return String(value || "").match(/^(\d{4}-\d{2}-\d{2})/)?.[1] || null;
}

function isExhibition(event) {
  const primaryId = String(event?.primary_category?.id || "").trim();
  if (EXHIBITION_IDS.has(primaryId)) return true;
  return (event?.categories || []).some((category) => EXHIBITION_IDS.has(String(category?.id || "").trim()));
}

function classifyClockRoles(text) {
  const result = {
    raw_times: [],
    session_times: [],
    event_end_time: null,
    doors_time: null,
    venue_hours: null,
  };

  for (const clause of String(text || "").split(CLAUSE_SPLIT_PATTERN)) {
    const clocks = [...clause.matchAll(CLOCK_PATTERN)];
    if (!clocks.length) continue;
    const markers = [...clause.matchAll(ROLE_MARKER_PATTERN)];
    const roles = clocks.map((clock) => {
      const preceding = markers.filter((marker) => marker.index < clock.index);
      if (!preceding.length) return null;
      const marker = preceding.at(-1);
      const markerText = marker[0] || "";
      const gap = clause.slice(marker.index + markerText.length, clock.index);
      if (/[.!?]/.test(gap)) return null;
      if (marker.groups?.venue) return "venue";
      if (marker.groups?.doors) return "doors";
      if (marker.groups?.session) return "session";
      return null;
    });

    clocks.forEach((clock, index) => {
      const value = validClock(clock[0]);
      if (!value) return;
      result.raw_times.push(value);
      const role = roles[index];

      const previous = index ? clocks[index - 1] : null;
      const previousSeparator = previous
        ? clause.slice(previous.index + previous[0].length, clock.index)
        : "";
      const isRangeEnd = Boolean(
        previous
        && roles[index - 1] === role
        && RANGE_SEPARATOR_PATTERN.test(previousSeparator)
      );

      const following = index + 1 < clocks.length ? clocks[index + 1] : null;
      const followingSeparator = following
        ? clause.slice(clock.index + clock[0].length, following.index)
        : "";
      const startsRange = Boolean(
        following
        && roles[index + 1] === role
        && RANGE_SEPARATOR_PATTERN.test(followingSeparator)
      );

      if (role === "venue") {
        if (startsRange && !isRangeEnd) {
          const closing = validClock(following[0]);
          result.venue_hours = {
            opening_time: value,
            closing_time: closing,
            display_text: `${value}–${closing}`,
          };
        }
        return;
      }

      if (role === "doors") {
        if (!isRangeEnd && !result.doors_time) result.doors_time = value;
        return;
      }

      if (role === "session") {
        if (isRangeEnd) result.event_end_time ||= value;
        else result.session_times.push(value);
        return;
      }

      const prefix = clause.slice(Math.max(0, clock.index - 18), clock.index);
      if (START_CUE_PATTERN.test(prefix)) result.session_times.push(value);
    });
  }

  result.raw_times = unique(result.raw_times);
  result.session_times = unique(result.session_times);
  return result;
}

function occurrenceSessions(schedule) {
  const occurrences = Array.isArray(schedule?.occurrences) ? schedule.occurrences : [];
  return {
    occurrences,
    sessionTimes: unique(occurrences.map((item) => timePart(item?.start))),
  };
}

function occurrenceEndTime(occurrences) {
  if (occurrences.length !== 1) return null;
  const occurrence = occurrences[0] || {};
  const startDay = datePart(occurrence.start);
  const endDay = datePart(occurrence.end);
  const startTime = timePart(occurrence.start);
  const endTime = endDay === startDay ? timePart(occurrence.end) : null;
  return endTime && endTime !== startTime ? endTime : null;
}

function legacyVenueHours(schedule, event, parsed) {
  const existing = schedule?.venue_hours ?? event?.venue_hours;
  if (existing && typeof existing === "object" && !Array.isArray(existing)) return { ...existing };
  if (typeof existing === "string" && existing.trim()) return { display_text: existing.trim() };

  const weekly = schedule?.opening_hours;
  if (weekly && typeof weekly === "object" && !Array.isArray(weekly)) return { ...weekly };

  const opening = validClock(schedule?.opening_time);
  const closing = validClock(schedule?.closing_time);
  if (opening && closing && opening !== closing) {
    return {
      opening_time: opening,
      closing_time: closing,
      display_text: `${opening}–${closing}`,
      confidence: schedule?.hours_confidence || null,
    };
  }

  const freeform = [schedule?.venue_opening_hours, schedule?.visit_hours, event?.location?.opening_hours]
    .map((value) => String(value || "").replace(/\s+/g, " ").trim())
    .find(Boolean);
  if (freeform) return { display_text: freeform };

  return parsed?.venue_hours ? { ...parsed.venue_hours } : null;
}

function deriveScheduleDisplay(sessionTimes, eventEndTime) {
  if (sessionTimes.length === 1 && eventEndTime) return `${sessionTimes[0]}–${eventEndTime}`;
  return naturalTimeList(sessionTimes);
}

function sameSchedule(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function normalizeEventScheduleContract(event) {
  if (!event || typeof event !== "object") return event;
  const schedule = { ...(event.schedule || {}) };
  const description = String(event.description || "");
  const legacyDisplay = String(schedule.display_text || "");
  const parsed = classifyClockRoles([description, legacyDisplay].filter(Boolean).join(" · "));

  const structured = occurrenceSessions(schedule);
  let sessionTimes;
  if (structured.occurrences.length) {
    // Dated occurrences are authoritative; the flat list is only a convenience.
    sessionTimes = structured.sessionTimes;
  } else {
    const explicit = Array.isArray(schedule.session_times)
      ? schedule.session_times
      : Array.isArray(event.session_times)
        ? event.session_times
        : [];
    sessionTimes = unique(explicit);
    if (!sessionTimes.length) sessionTimes = parsed.session_times;

    const timedStart = timePart(schedule.start);
    const mode = String(schedule.mode || "").toLocaleLowerCase("en");
    if (
      !sessionTimes.length
      && timedStart
      && !isExhibition(event)
      && !["multi_day", "ongoing", "permanent"].includes(mode)
    ) {
      sessionTimes = [timedStart];
    }
  }

  let eventEndTime = validClock(schedule.event_end_time || event.event_end_time);
  if (!eventEndTime) eventEndTime = occurrenceEndTime(structured.occurrences);
  if (!eventEndTime && structured.occurrences.length === 0 && sessionTimes.length === 1) {
    const startDay = datePart(schedule.start);
    const endDay = datePart(schedule.end);
    const startTime = timePart(schedule.start);
    const endTime = startDay && endDay === startDay ? timePart(schedule.end) : null;
    if (endTime && endTime !== startTime) eventEndTime = endTime;
  }
  if (!eventEndTime) eventEndTime = parsed.event_end_time;

  const doorsTime = validClock(schedule.doors_time || event.doors_time) || parsed.doors_time;
  const venueHours = legacyVenueHours(schedule, event, parsed);
  const scheduleDisplay = deriveScheduleDisplay(sessionTimes, eventEndTime);

  const normalized = {
    ...schedule,
    schedule_contract_version: "1.0",
    session_times: sessionTimes,
    event_end_time: eventEndTime || null,
    doors_time: doorsTime || null,
    venue_hours: venueHours,
    schedule_display: scheduleDisplay,
  };

  // Keep legacy opening_hours readable during the migration. New logic consumes
  // venue_hours first; older date-aware modules continue to work safely.
  if (!normalized.opening_hours && venueHours?.opening_time && venueHours?.closing_time) {
    normalized.opening_hours = { ...venueHours };
  }

  if (sameSchedule(schedule, normalized)) return event;
  return { ...event, schedule: normalized };
}

export function normalizeScheduleContractDataset(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    const normalized = normalizeEventScheduleContract(event);
    if (normalized !== event) changed = true;
    return normalized;
  });
  return changed ? { ...dataset, events } : dataset;
}

export { classifyClockRoles, naturalTimeList, validClock };
