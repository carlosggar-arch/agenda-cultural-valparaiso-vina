const HTML_ENTITY_RX = /&(?:#(?:x[0-9a-f]+|\d+)|[a-z][a-z0-9]+);/giu;
const TAG_SHAPED_RX = /<\/?[A-Za-z][^>]*>/g;
const SCRIPT_STYLE_RX = /<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/giu;
const COMMENT_RX = /<!--[\s\S]*?-->/g;
const BREAK_RX = /<(?:br\s*\/?)>/giu;
const BLOCK_BOUNDARY_RX = /<\/?(?:p|div|section|article|header|footer|main|aside|nav|li|ul|ol|h[1-6]|blockquote|pre|table|thead|tbody|tfoot|tr|td|th|figure|figcaption|details|summary)\b[^>]*>/giu;
const DESCRIPTION_WORD_RX = /[\p{L}\p{M}]+(?:['’.-][\p{L}\p{M}]+)*/gu;
const DESCRIPTION_CLAUSE_BREAK = /[|:;.!?¿¡—–]\s*["“”'‘’«»‹›()\[\]{}]*$/u;
const DESCRIPTION_ACRONYMS = new Set([
  "AI", "CMI", "DJ", "DJS", "FETEN", "FICX", "FMCE", "IA", "LGBT", "LGBTQ", "MNHN", "ONU", "PUCV",
  "SCD", "SIDA", "UAI", "UNESCO", "UP", "USM", "UTFSM", "UV", "VIH",
]);
const ROMAN_NUMERAL = /^(?=[IVXLCDM]+$)M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$/u;

const NAMED_ENTITIES = Object.freeze({
  amp: "&",
  apos: "'",
  gt: ">",
  hellip: "…",
  laquo: "«",
  ldquo: "“",
  lsquo: "‘",
  nbsp: " ",
  quot: '"',
  raquo: "»",
  rdquo: "”",
  rsquo: "’",
  lt: "<",
});

function decodeEntity(entity) {
  const body = entity.slice(1, -1);
  if (/^#x/i.test(body)) {
    const code = Number.parseInt(body.slice(2), 16);
    return Number.isFinite(code) && code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : entity;
  }
  if (/^#\d+$/.test(body)) {
    const code = Number.parseInt(body.slice(1), 10);
    return Number.isFinite(code) && code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : entity;
  }
  return NAMED_ENTITIES[body.toLocaleLowerCase("en")] ?? entity;
}

export function decodePublicHtmlEntities(value) {
  let text = String(value ?? "");
  // A few feeds double-encode snippets (&amp;lt;p&amp;gt;). Decode in bounded
  // passes so encoded markup is normalized before it is stripped.
  for (let pass = 0; pass < 3; pass += 1) {
    const next = text.replace(HTML_ENTITY_RX, decodeEntity);
    if (next === text) break;
    text = next;
  }
  return text;
}

export function plainPublicText(value) {
  if (value === null || value === undefined) return "";
  let text = decodePublicHtmlEntities(value);
  text = text.replace(SCRIPT_STYLE_RX, " ");
  text = text.replace(COMMENT_RX, " ");
  text = text.replace(BREAK_RX, " ");
  text = text.replace(BLOCK_BOUNDARY_RX, " ");
  text = text.replace(TAG_SHAPED_RX, " ");
  return text.replace(/\s+/g, " ").trim();
}

function casedLetters(value) {
  return [...String(value || "")].filter((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
}

function isAllCapsWord(value) {
  const letters = casedLetters(value);
  return letters.length > 0 && letters.every((char) => char === char.toLocaleUpperCase("es"));
}

function protectedUpperToken(value) {
  const upper = String(value || "").toLocaleUpperCase("es");
  return DESCRIPTION_ACRONYMS.has(upper) || ROMAN_NUMERAL.test(upper);
}

function upperFirst(value) {
  const chars = [...String(value || "")];
  const index = chars.findIndex((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  if (index >= 0) chars[index] = chars[index].toLocaleUpperCase("es");
  return chars.join("");
}

function normalizeUpperRun(text, run) {
  const start = run[0].index;
  const last = run.at(-1);
  const end = last.index + last[0].length;
  const source = text.slice(start, end);
  let cursor = start;
  let output = "";

  run.forEach((match, index) => {
    const between = text.slice(cursor, match.index);
    output += between;
    const token = match[0];
    if (protectedUpperToken(token)) {
      output += token.toLocaleUpperCase("es");
    } else {
      const lower = token.toLocaleLowerCase("es");
      const capitalize = index === 0 || DESCRIPTION_CLAUSE_BREAK.test(between);
      output += capitalize ? upperFirst(lower) : lower;
    }
    cursor = match.index + token.length;
  });
  output += text.slice(cursor, end);
  return { start, end, source, value: output };
}

/**
 * Convert promotional all-caps runs in descriptions to readable sentence case.
 * Mixed-case prose is untouched. Acronyms and Roman numerals remain uppercase,
 * and clause separators such as | start a fresh capitalized phrase.
 */
export function normalizePublicDescriptionCase(value) {
  const text = String(value ?? "");
  const words = [...text.matchAll(DESCRIPTION_WORD_RX)];
  if (words.length < 2) return text;

  const runs = [];
  let current = [];
  const flush = () => {
    if (current.length >= 2) {
      const letters = current.reduce((total, match) => total + casedLetters(match[0]).length, 0);
      const hasEditable = current.some((match) => !protectedUpperToken(match[0]));
      if (letters >= 7 && hasEditable) runs.push(current);
    }
    current = [];
  };

  for (const match of words) {
    if (isAllCapsWord(match[0])) current.push(match);
    else flush();
  }
  flush();
  if (!runs.length) return text;

  let output = text;
  const replacements = runs.map((run) => normalizeUpperRun(text, run));
  for (const replacement of replacements.reverse()) {
    output = `${output.slice(0, replacement.start)}${replacement.value}${output.slice(replacement.end)}`;
  }
  return output;
}

function cleanStringProperty(target, key) {
  if (!target || typeof target[key] !== "string") return target;
  const cleaned = plainPublicText(target[key]);
  if (cleaned === target[key]) return target;
  return { ...target, [key]: cleaned };
}

function cleanDescriptionProperty(target) {
  if (!target || typeof target.description !== "string") return target;
  const cleaned = normalizePublicDescriptionCase(plainPublicText(target.description));
  if (cleaned === target.description) return target;
  return { ...target, description: cleaned };
}

function cleanCategory(category) {
  return cleanStringProperty(category, "label");
}

function cleanSchedule(schedule) {
  if (!schedule || typeof schedule !== "object") return schedule;
  let next = schedule;
  for (const key of ["display_text", "venue_opening_hours", "visit_hours"]) next = cleanStringProperty(next, key);

  if (schedule.opening_hours && typeof schedule.opening_hours === "object") {
    const openingHours = cleanStringProperty(schedule.opening_hours, "display_text");
    if (openingHours !== schedule.opening_hours) next = { ...next, opening_hours: openingHours };
  }

  if (Array.isArray(schedule.occurrences)) {
    let occurrencesChanged = false;
    const occurrences = schedule.occurrences.map((occurrence) => {
      const cleaned = cleanStringProperty(occurrence, "display_text");
      if (cleaned !== occurrence) occurrencesChanged = true;
      return cleaned;
    });
    if (occurrencesChanged) next = { ...next, occurrences };
  }
  return next;
}

function cleanLocation(location) {
  if (!location || typeof location !== "object") return location;
  let next = location;
  for (const key of ["venue", "city", "commune", "address", "opening_hours"]) next = cleanStringProperty(next, key);
  return next;
}

function cleanEvent(event) {
  if (!event || typeof event !== "object") return event;
  let next = event;
  for (const key of ["title", "organizer", "source_name", "registration_requirements", "audience"]) {
    next = cleanStringProperty(next, key);
  }
  next = cleanDescriptionProperty(next);

  if (event.primary_category) {
    const primary = cleanCategory(event.primary_category);
    if (primary !== event.primary_category) next = { ...next, primary_category: primary };
  }

  if (Array.isArray(event.categories)) {
    let categoriesChanged = false;
    const categories = event.categories.map((category) => {
      const cleaned = cleanCategory(category);
      if (cleaned !== category) categoriesChanged = true;
      return cleaned;
    });
    if (categoriesChanged) next = { ...next, categories };
  }

  const schedule = cleanSchedule(event.schedule);
  if (schedule !== event.schedule) next = { ...next, schedule };
  const location = cleanLocation(event.location);
  if (location !== event.location) next = { ...next, location };

  if (event.price && typeof event.price === "object") {
    const price = cleanStringProperty(event.price, "display_text");
    if (price !== event.price) next = { ...next, price };
  }

  if (event.public_status && typeof event.public_status === "object") {
    const status = cleanStringProperty(event.public_status, "advisory_text");
    if (status !== event.public_status) next = { ...next, public_status: status };
  }

  if (event.image && typeof event.image === "object") {
    const image = cleanStringProperty(event.image, "alt");
    if (image !== event.image) next = { ...next, image };
  }

  if (Array.isArray(event.tags)) {
    const tags = event.tags.map((tag) => typeof tag === "string" ? plainPublicText(tag) : tag);
    if (tags.some((tag, index) => tag !== event.tags[index])) next = { ...next, tags };
  }

  return next;
}

export function normalizeAgendaPublicText(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = dataset.events.map((event) => {
    const cleaned = cleanEvent(event);
    if (cleaned !== event) changed = true;
    return cleaned;
  });
  return changed ? { ...dataset, events } : dataset;
}
