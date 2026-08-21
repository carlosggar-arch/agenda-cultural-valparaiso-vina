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

function activityCategoryId(event) {
  return cleanSpace(event?.primary_category?.id || event?.categories?.[0]?.id).toLocaleLowerCase("es");
}

function stripRedundantFormatPrefix(value, event) {
  let text = cleanSpace(value);
  const categoryId = activityCategoryId(event);
  if (categoryId !== "cursos-talleres-campus" && categoryId !== "cursos-talleres") return text;
  const candidate = text.replace(
    /^ciclo\s+(?:de\s+)?taller(?:es)?\s*(?:(?:[:|/–—-])\s*)?/iu,
    "",
  ).trim();
  return viableTitle(candidate) || text;
}

function stripEmbeddedCityStop(value, event) {
  let text = cleanSpace(value);
  const city = cleanSpace(event?.location?.city);
  if (!city) return text;
  const cityRx = flexibleLiteral(city);

  // Location is metadata, not part of the public title. This covers tour/listing
  // forms such as "INUNDAREMOS EN VALPARAÍSO - GIRA TANQUEMANTE" without
  // blindly removing every occurrence of the preposition "en".
  text = text.replace(
    new RegExp(`^(.+?)\\s+en\\s+${cityRx}\\s*([-–—:])\\s*(.+)$`, "iu"),
    (_match, before, separator, after) => `${before.trim()} ${separator === ":" ? ":" : "—"} ${after.trim()}`,
  );
  text = text.replace(
    new RegExp(`^(.+?)\\s+en\\s+${cityRx}\\s*$`, "iu"),
    (_match, before) => before.trim(),
  );
  return text;
}

function exactLocationSuffixMatches(value, event) {
  const suffix = fold(value);
  const venue = cleanSpace(event?.location?.venue);
  const city = cleanSpace(event?.location?.city);
  if (!suffix) return false;
  if (venue && suffix === fold(venue)) return true;
  if (city && suffix === fold(city)) return true;
  return Boolean(venue && city && suffix === fold(`${venue} ${city}`));
}

function stripExactLocationSuffix(value, event) {
  const text = cleanSpace(value);
  const patterns = [
    /^(.+)\s+(?:en|@)\s+(.+)$/iu,
    /^(.+)\s*(?:\/\/|[:|·/–—-])\s*(.+)$/u,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (!match || !exactLocationSuffixMatches(match[2], event)) continue;
    const candidate = viableTitle(match[1]);
    if (candidate) return candidate;
  }
  return text;
}

function isAllCaps(value) {
  const letters = [...String(value || "")]
    .filter((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  return letters.length >= 5 && letters.every((char) => char === char.toLocaleUpperCase("es"));
}

function upperFirst(value) {
  const chars = [...String(value || "").toLocaleLowerCase("es")];
  const index = chars.findIndex((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  if (index >= 0) chars[index] = chars[index].toLocaleUpperCase("es");
  return chars.join("");
}

function titleCaseTourName(value) {
  const minor = new Set(["a", "al", "de", "del", "el", "en", "la", "las", "los", "y"]);
  return cleanSpace(value).toLocaleLowerCase("es").split(" ").map((word, index) => {
    if (index > 0 && minor.has(word)) return word;
    return word ? `${word[0].toLocaleUpperCase("es")}${word.slice(1)}` : word;
  }).join(" ");
}

function normalizeStructuredAllCaps(value) {
  const text = cleanSpace(value);
  if (!isAllCaps(text)) return text;
  const tour = text.match(/^(.+?)\s+[—–-]\s+GIRA\s+(.+)$/u);
  if (tour) return `${upperFirst(tour[1])} — Gira ${titleCaseTourName(tour[2])}`;
  return text;
}

export function normalizePublicTitle(value, event = null) {
  let text = cleanSpace(value);
  if (!text || !event) return text;

  text = stripRedundantFormatPrefix(text, event);
  text = stripEmbeddedCityStop(text, event);
  text = stripExactLocationSuffix(text, event);

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
  return normalizeStructuredAllCaps(text);
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
  const openingHours = schedule.opening_hours || {};
  const opening = cleanSpace(schedule.opening_time || openingHours.opening_time);
  const closing = cleanSpace(schedule.closing_time || openingHours.closing_time);
  if (/^\d{2}:\d{2}$/.test(opening) && /^\d{2}:\d{2}$/.test(closing)) return `${opening}–${closing}`;
  const display = cleanSpace(openingHours.display_text || schedule.display_text);
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
