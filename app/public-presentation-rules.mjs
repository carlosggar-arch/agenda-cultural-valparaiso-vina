function cleanSpace(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function fold(value) {
  return cleanSpace(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function flexibleLiteral(value) {
  return escapeRegExp(cleanSpace(value)).replace(/\\\s+/g, "\\s+");
}

function addAlias(target, value, city) {
  const alias = cleanSpace(value).replace(/^[,·|/–—-]+|[,·|/–—-]+$/gu, "").trim();
  if (!alias) return;
  target.add(alias);
  if (city) {
    const cityRx = flexibleLiteral(city);
    const withoutCity = alias.replace(new RegExp(`\\s*[,·]\\s*${cityRx}\\s*$`, "iu"), "").trim();
    if (withoutCity && withoutCity !== alias) target.add(withoutCity);
  }
}

export function venueAliases(event) {
  const venue = cleanSpace(event?.location?.venue);
  const city = cleanSpace(event?.location?.city);
  const aliases = new Set();
  addAlias(aliases, venue, city);
  for (const part of venue.split(/\s+(?:[·|/]|[-–—])\s+/u)) addAlias(aliases, part, city);
  if (city) aliases.add(city);
  return [...aliases].sort((a, b) => b.length - a.length);
}

function viableTitle(value) {
  const text = cleanSpace(value).replace(/^[,·|/:–—-]+|[,·|/:–—-]+$/gu, "").trim();
  return fold(text).length >= 4 ? text : null;
}

export function normalizePublicTitle(value, event = null) {
  let text = cleanSpace(value);
  if (!text || !event) return text;

  const city = cleanSpace(event?.location?.city);
  const cityRx = city ? flexibleLiteral(city) : null;

  for (let pass = 0; pass < 2; pass += 1) {
    const before = text;
    for (const alias of venueAliases(event)) {
      const aliasRx = flexibleLiteral(alias);
      const optionalCity = cityRx && fold(alias) !== fold(city)
        ? `(?:\\s*[,·]\\s*${cityRx})?`
        : "";
      const patterns = [
        new RegExp(`^${aliasRx}${optionalCity}\\s*(?:[:|·/–—-])\\s*(.+)$`, "iu"),
        new RegExp(`^(.+?)\\s+(?:en|@)\\s+${aliasRx}${optionalCity}\\s*$`, "iu"),
        new RegExp(`^(.+?)\\s*(?:[:|·/–—-])\\s*${aliasRx}${optionalCity}\\s*$`, "iu"),
      ];
      let changed = false;
      for (const pattern of patterns) {
        const match = text.match(pattern);
        const candidate = match ? viableTitle(match[1]) : null;
        if (!candidate) continue;
        text = candidate;
        changed = true;
        break;
      }
      if (changed) break;
    }
    if (text === before) break;
  }
  return text;
}

export function isNonEventDescription(value) {
  const text = fold(value);
  if (!text) return false;
  return [
    /^cobertura municipal oficial de programacion de\b/,
    /^cobertura oficial (?:municipal )?de programacion de\b/,
    /^evento detectado en .+ utilizado como ticketera y fuente secundaria\b/,
    /^evento detectado en .+ utilizado como fuente secundaria\b/,
    /^evento recuperado desde .+ como fuente secundaria\b/,
  ].some((pattern) => pattern.test(text));
}

export function publicLocationLabel(event) {
  const venue = cleanSpace(event?.location?.venue);
  const city = cleanSpace(event?.location?.city);
  if (venue && city) {
    const venueFolded = fold(venue);
    const cityFolded = fold(city);
    if (venueFolded === cityFolded || venueFolded.endsWith(` ${cityFolded}`)) return venue;
    return `${venue} · ${city}`;
  }
  return venue || city || "Lugar por confirmar";
}

function dateKey(value, timezone) {
  if (!value) return null;
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function formatDate(value, locale, timezone, weekday = false) {
  const key = dateKey(value, timezone);
  if (!key) return cleanSpace(value);
  const [year, month, day] = key.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, {
    timeZone: "UTC",
    weekday: weekday ? "short" : undefined,
    day: "numeric",
    month: "short",
  }).format(new Date(Date.UTC(year, month - 1, day, 12)));
}

function formatTime(value, locale, timezone) {
  if (!value || /^\d{4}-\d{2}-\d{2}$/.test(String(value))) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(locale, {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function visitHours(event) {
  const schedule = event?.schedule || {};
  const opening = cleanSpace(schedule.opening_time);
  const closing = cleanSpace(schedule.closing_time);
  if (/^\d{2}:\d{2}$/.test(opening) && /^\d{2}:\d{2}$/.test(closing)) return `${opening}–${closing}`;
  const display = cleanSpace(schedule.display_text);
  const range = display.match(/\b([01]?\d|2[0-3]):[0-5]\d\s*[–—-]\s*([01]?\d|2[0-3]):[0-5]\d\b/u);
  if (range) return range[0].replace(/\s*[–—-]\s*/u, "–");
  return null;
}

export function groupedScheduleLabel(event, options = {}) {
  const locale = options.locale || "es-CL";
  const timezone = options.timezone || "America/Santiago";
  const now = options.now instanceof Date ? options.now : new Date();
  const schedule = event?.schedule || {};
  const start = schedule.start || schedule.occurrences?.[0]?.start;
  const end = schedule.end;
  const hours = visitHours(event);
  if (!start) return cleanSpace(schedule.display_text) || "Horario por confirmar";

  const startKey = dateKey(start, timezone);
  const endKey = dateKey(end, timezone);
  const todayKey = dateKey(now, timezone);
  if (startKey && endKey && startKey !== endKey) {
    const dates = startKey <= todayKey && endKey >= todayKey
      ? `En exhibición hasta el ${formatDate(end, locale, timezone)}`
      : `${formatDate(start, locale, timezone)} – ${formatDate(end, locale, timezone)}`;
    return hours ? `${dates} · ${hours}` : dates;
  }

  const date = formatDate(start, locale, timezone, true);
  if (hours) return `${date} · ${hours}`;
  const time = formatTime(start, locale, timezone);
  return time ? `${date} · ${time}` : date || cleanSpace(schedule.display_text) || "Horario por confirmar";
}
