export const LIFECYCLE_STATES = Object.freeze({
  UPCOMING: "upcoming",
  LIVE: "live",
  STARTED: "started",
  ONGOING: "ongoing",
  ENDED: "ended",
  ALWAYS_AVAILABLE: "always_available",
  UNDATED: "undated",
});

const WALL_CLOCK_FORMATTERS = new Map();

function wallClockFormatter(timeZone) {
  if (!WALL_CLOCK_FORMATTERS.has(timeZone)) {
    WALL_CLOCK_FORMATTERS.set(timeZone, new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }));
  }
  return WALL_CLOCK_FORMATTERS.get(timeZone);
}

export function cityWallClock(value = new Date(), timeZone = "UTC") {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const parts = wallClockFormatter(timeZone).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  const year = get("year");
  const month = get("month");
  const day = get("day");
  if (!year || !month || !day) return null;
  return {
    day: `${year}-${month}-${day}`,
    hour: Number(get("hour")),
    minute: Number(get("minute")),
    second: Number(get("second")),
    instant: date,
  };
}

function isDateOnly(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || "").trim());
}

function dateKeyForDate(value, timeZone) {
  return cityWallClock(value, timeZone)?.day || null;
}

function dateKeyForValue(value, timeZone) {
  const text = String(value || "").trim();
  if (!text) return null;
  if (isDateOnly(text)) return text;
  return dateKeyForDate(text, timeZone);
}

function parsedInstant(value) {
  const text = String(value || "").trim();
  if (!text || isDateOnly(text)) return null;
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function datedWindows(event) {
  if (["program", "flexible_offer", "recurring_offer", "permanent_offer"].includes(event?.event_type)) return [];
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.some((occurrence) => occurrence?.start)) {
    return occurrences
      .filter((occurrence) => occurrence?.start)
      .map((occurrence) => ({ start: occurrence.start, end: occurrence.end || null }));
  }
  if (event?.schedule?.start) {
    return [{ start: event.schedule.start, end: event.schedule.end || null }];
  }
  return [];
}

function lifecycleForWindow(window, { now, timeZone }) {
  const wall = cityWallClock(now, timeZone);
  if (!wall || !window?.start) return { state: LIFECYCLE_STATES.UNDATED, visible: true };

  const startText = String(window.start || "").trim();
  const startDay = dateKeyForValue(startText, timeZone);
  if (!startDay) return { state: LIFECYCLE_STATES.UNDATED, visible: true };

  if (!isDateOnly(startText)) {
    const start = parsedInstant(startText);
    if (!start) return { state: LIFECYCLE_STATES.UNDATED, visible: true };
    const endText = String(window.end || "").trim();
    const endDay = dateKeyForValue(endText, timeZone) || startDay;

    if (now.getTime() < start.getTime()) {
      return { state: LIFECYCLE_STATES.UPCOMING, visible: true, start };
    }

    if (wall.day > endDay) {
      return { state: LIFECYCLE_STATES.ENDED, visible: false, start, startDay, endDay };
    }

    const end = endText && !isDateOnly(endText) ? parsedInstant(endText) : null;
    if (end && now.getTime() <= end.getTime()) {
      return { state: LIFECYCLE_STATES.LIVE, visible: true, start, end, startDay, endDay };
    }
    return {
      state: endDay > startDay ? LIFECYCLE_STATES.ONGOING : LIFECYCLE_STATES.STARTED,
      visible: true,
      start,
      end,
      startDay,
      endDay,
    };
  }

  const endDay = dateKeyForValue(window.end, timeZone) || startDay;
  if (wall.day < startDay) {
    return { state: LIFECYCLE_STATES.UPCOMING, visible: true, startDay, endDay };
  }
  if (wall.day <= endDay) {
    return { state: LIFECYCLE_STATES.ONGOING, visible: true, startDay, endDay };
  }
  return { state: LIFECYCLE_STATES.ENDED, visible: false, startDay, endDay };
}

export function eventLifecycle(event, {
  now = new Date(),
  timeZone = event?.schedule?.timezone || "UTC",
} = {}) {
  const type = String(event?.event_type || "").toLowerCase();
  if (["program", "flexible_offer", "recurring_offer", "permanent_offer"].includes(type)) {
    return { state: LIFECYCLE_STATES.ALWAYS_AVAILABLE, visible: true, timeZone };
  }

  const instant = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(instant.getTime())) return { state: LIFECYCLE_STATES.UNDATED, visible: true, timeZone };
  const windows = datedWindows(event);
  if (!windows.length) return { state: LIFECYCLE_STATES.UNDATED, visible: true, timeZone };
  const states = windows.map((window) => lifecycleForWindow(window, { now: instant, timeZone }));

  for (const preferred of [
    LIFECYCLE_STATES.LIVE,
    LIFECYCLE_STATES.STARTED,
    LIFECYCLE_STATES.ONGOING,
    LIFECYCLE_STATES.UPCOMING,
  ]) {
    const match = states.find((state) => state.state === preferred);
    if (match) return { ...match, timeZone };
  }
  return { ...states[states.length - 1], state: LIFECYCLE_STATES.ENDED, visible: false, timeZone };
}

export function eventIsCurrentOrFuture(event, {
  now = new Date(),
  timeZone = event?.schedule?.timezone || "UTC",
} = {}) {
  return eventLifecycle(event, { now, timeZone }).visible;
}

function pruneExpiredOccurrences(event, { now, timeZone }) {
  if (["program", "flexible_offer", "recurring_offer", "permanent_offer"].includes(event?.event_type)) return event;
  const schedule = event?.schedule;
  const occurrences = schedule?.occurrences;
  if (!Array.isArray(occurrences) || !occurrences.length) return event;

  const currentOrFuture = occurrences.filter((occurrence) => lifecycleForWindow(
    { start: occurrence?.start, end: occurrence?.end || null },
    { now, timeZone },
  ).visible);
  if (!currentOrFuture.length) return null;
  if (currentOrFuture.length === occurrences.length) return event;

  const first = currentOrFuture[0];
  const last = currentOrFuture[currentOrFuture.length - 1];
  return {
    ...event,
    schedule: {
      ...schedule,
      start: first?.start || schedule.start,
      end: last?.end || last?.start || first?.end || first?.start || schedule.end,
      occurrences: currentOrFuture,
      display_text: null,
    },
  };
}

export function removeExpiredDatedEvents(dataset, {
  now = new Date(),
  timeZone = dataset?.timezone || "UTC",
} = {}) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const instant = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(instant.getTime())) return dataset;

  const events = dataset.events
    .map((event) => pruneExpiredOccurrences(event, { now: instant, timeZone }))
    .filter(Boolean)
    .filter((event) => eventIsCurrentOrFuture(event, { now: instant, timeZone }));

  return events.length === dataset.events.length && events.every((event, index) => event === dataset.events[index])
    ? dataset
    : { ...dataset, events };
}

export function filterVisibleDataset(dataset, city = null, now = new Date()) {
  return removeExpiredDatedEvents(dataset, {
    now,
    timeZone: city?.timezone || dataset?.timezone || "UTC",
  });
}
