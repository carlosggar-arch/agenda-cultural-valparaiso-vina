import { cityWallClock } from "./runtime-past-event-guard.mjs?v=20260823-pastguard5";

const MAX_SEARCH_MS = 36 * 60 * 60 * 1000;

export function localDayKey(now = new Date(), timeZone = "UTC") {
  return cityWallClock(now, timeZone)?.day || null;
}

export function millisecondsUntilNextLocalDay(now = new Date(), timeZone = "UTC") {
  const instant = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(instant.getTime())) return 60_000;
  const currentDay = localDayKey(instant, timeZone);
  if (!currentDay) return 60_000;

  const start = instant.getTime();
  let low = start;
  let high = start + MAX_SEARCH_MS;
  if (localDayKey(new Date(high), timeZone) === currentDay) return MAX_SEARCH_MS;

  while (high - low > 1_000) {
    const middle = Math.floor((low + high) / 2);
    if (localDayKey(new Date(middle), timeZone) === currentDay) low = middle;
    else high = middle;
  }
  return Math.max(1_000, high - start + 250);
}
