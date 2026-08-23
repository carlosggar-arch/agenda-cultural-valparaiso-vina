export const POINT_EVENT_VISIBILITY_HOURS = 4;

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

function formatter(timezone) {
  if (!WALL_CLOCK_FORMATTERS.has(timezone)) {
    WALL_CLOCK_FORMATTERS.set(timezone, new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }));
  }
  return WALL_CLOCK_FORMATTERS.get(timezone);
}

export function cityWallClock(now = new Date(), timezone = "America/Santiago") {
  const date = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(date.getTime())) return null;
  const parts = formatter(timezone).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  const day = `${get("year")}-${get("month")}-${get("day")}`;
  return {
    day,
    hour: Number(get("hour")),
    minute: Number(get("minute")),
    second: Number(get("second")),
    instant: date,
  };
}

function isDateOnly(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || "").trim());
}

function dateKey(value, timezone) {
  const text = String(value || "").trim();
  if (isDateOnly(text)) return text;
  const parsed = new Date(text);
  return cityWallClock(parsed, timezone)?.day || null;
}

function parsedInstant(value) {
  const text = String(value || "").trim();
  if (!text || isDateOnly(text)) return null;
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function compareDay(left, right) {
  return String(left || "").localeCompare(String(right || ""));
}

function pointVisibilityUntil(start, explicitEnd = null) {
  if (explicitEnd instanceof Date && explicitEnd.getTime() > start.getTime()) return explicitEnd;
  return new Date(start.getTime() + POINT_EVENT_VISIBILITY_HOURS * 60 * 60 * 1000);
}

function lifecycleForWindow(window, now, timezone) {
  const wall = cityWallClock(now, timezone);
  if (!wall || !window?.start) return { state: LIFECYCLE_STATES.UNDATED, visible: true };

  const startText = String(window.start);
  const startDay = dateKey(startText, timezone);
  if (!startDay) return { state: LIFECYCLE_STATES.UNDATED, visible: true };

  const timed = !isDateOnly(startText);
  if (timed) {
    const start = parsedInstant(startText);
    if (!start) return { state: LIFECYCLE_STATES.UNDATED, visible: true };
    let end = null;
    const endText = String(window.end || "").trim();
    if (endText) {
      const endDateOnlySameDay = isDateOnly(endText) && endText === startDay;
      if (!endDateOnlySameDay) end = parsedInstant(endText);
    }
    if (now.getTime() < start.getTime()) {
      return { state: LIFECYCLE_STATES.UPCOMING, visible: true, start, end };
    }
    const visibilityUntil = pointVisibilityUntil(start, end);
    if (now.getTime() <= visibilityUntil.getTime()) {
      return {
        state: end ? LIFECYCLE_STATES.LIVE : LIFECYCLE_STATES.STARTED,
        visible: true,
        start,
        end,
        visibilityUntil,
      };
    }
    return {
      state: LIFECYCLE_STATES.ENDED,
      visible: false,
      start,
      end,
      visibilityUntil,
    };
  }

  const endDay = dateKey(window.end, timezone) || startDay;
  if (compareDay(wall.day, startDay) < 0) {
    return { state: LIFECYCLE_STATES.UPCOMING, visible: true, startDay, endDay };
  }
  if (compareDay(wall.day, endDay) <= 0) {
    return { state: LIFECYCLE_STATES.ONGOING, visible: true, startDay, endDay };
  }
  return { state: LIFECYCLE_STATES.ENDED, visible: false, startDay, endDay };
}

function scheduleWindows(event) {
  const occurrences = event?.schedule?.occurrences;
  if (Array.isArray(occurrences) && occurrences.some((item) => item?.start)) {
    return occurrences.filter((item) => item?.start).map((item) => ({
      start: item.start,
      end: item.end || null,
    }));
  }
  if (event?.schedule?.start) {
    return [{ start: event.schedule.start, end: event.schedule.end || null }];
  }
  return [];
}

export function eventLifecycle(event, city, now = new Date(), datasetTimezone = null) {
  const timezone = String(city?.timezone || datasetTimezone || event?.schedule?.timezone || "America/Santiago");
  const eventType = String(event?.event_type || "").toLocaleLowerCase("en");
  if (["flexible_offer", "recurring_offer", "permanent_offer"].includes(eventType)) {
    return { state: LIFECYCLE_STATES.ALWAYS_AVAILABLE, visible: true, timezone };
  }

  const windows = scheduleWindows(event);
  if (!windows.length) return { state: LIFECYCLE_STATES.UNDATED, visible: true, timezone };
  const instant = now instanceof Date ? now : new Date(now);
  const states = windows.map((window) => lifecycleForWindow(window, instant, timezone));
  for (const preferred of [
    LIFECYCLE_STATES.LIVE,
    LIFECYCLE_STATES.STARTED,
    LIFECYCLE_STATES.ONGOING,
    LIFECYCLE_STATES.UPCOMING,
  ]) {
    const match = states.find((state) => state.state === preferred);
    if (match) return { ...match, timezone };
  }
  return { ...states[states.length - 1], state: LIFECYCLE_STATES.ENDED, visible: false, timezone };
}

export function eventIsVisible(event, city, now = new Date(), datasetTimezone = null) {
  return eventLifecycle(event, city, now, datasetTimezone).visible;
}

export function filterVisibleEvents(events, city, now = new Date(), datasetTimezone = null) {
  return (events || []).filter((event) => eventIsVisible(event, city, now, datasetTimezone));
}

export function filterVisibleDataset(dataset, city, now = new Date()) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const events = filterVisibleEvents(dataset.events, city, now, dataset.timezone);
  if (events.length === dataset.events.length) return dataset;
  return { ...dataset, events };
}
