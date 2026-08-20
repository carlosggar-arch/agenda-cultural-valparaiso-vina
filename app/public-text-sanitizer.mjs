const HTML_ENTITY_RX = /&(?:#(?:x[0-9a-f]+|\d+)|[a-z][a-z0-9]+);/giu;
const TAG_SHAPED_RX = /<\/?[A-Za-z][^>]*>/g;
const SCRIPT_STYLE_RX = /<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/giu;
const COMMENT_RX = /<!--[\s\S]*?-->/g;
const BREAK_RX = /<(?:br\s*\/?)>/giu;
const BLOCK_BOUNDARY_RX = /<\/?(?:p|div|section|article|header|footer|main|aside|nav|li|ul|ol|h[1-6]|blockquote|pre|table|thead|tbody|tfoot|tr|td|th|figure|figcaption|details|summary)\b[^>]*>/giu;

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

function cleanStringProperty(target, key) {
  if (!target || typeof target[key] !== "string") return target;
  const cleaned = plainPublicText(target[key]);
  if (cleaned === target[key]) return target;
  return { ...target, [key]: cleaned };
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
  for (const key of ["title", "description", "organizer", "source_name", "registration_requirements", "audience"]) {
    next = cleanStringProperty(next, key);
  }

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
