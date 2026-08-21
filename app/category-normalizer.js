import { resolvePublicCategory } from "./public-category-rules.mjs?v=20260820-shared-training1";
import { normalizeVenueAliases } from "./venue-identity.mjs?v=20260819-venue1";

const QUOTED_ACTIVITY = [
  /“([^”]{3,140})”/g,
  /"([^"\n]{3,140})"/g,
  /«([^»]{3,140})»/g,
];
const ACTIVITY_TERMS = /\b(?:exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla|conversatorio|funci[oó]n|espect[aá]culo|presentaci[oó]n|encuentro|visita guiada|seminario|curso)\b/iu;
const EXHIBITION_TERMS = /\b(?:exposici[oó]n|muestra)\b/iu;
const FOLLOWING_TITLE_VERBS = /^\s*(?:lleg[oóa]|llega|se presenta|se exhibe|se inaugura|se realizar[aá]|se realiza|se presentar[aá]|se podr[aá] ver|abre|estar[aá]|vuelve)\b/iu;

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function cleanCandidate(value) {
  return String(value || "").replace(/\s+/g, " ").trim().replace(/[ .,:;–—-]+$/u, "").trim();
}

function titleIsVenue(event) {
  const title = fold(event?.title);
  const location = event?.location || {};
  const venue = fold(location.venue);
  const city = fold(location.city);
  const source = fold(event?.source_name);
  const organizer = fold(event?.organizer);
  if (!title || !venue) return false;
  if (title === venue) return true;
  if (city && (title === `${venue} ${city}` || title === `${city} ${venue}`)) return true;
  return title === venue && (title === source || title === organizer);
}

function recoverExplicitActivityTitle(event) {
  if (!titleIsVenue(event)) return null;
  const description = String(event?.description || "").trim();
  if (!description) return null;
  const venue = fold(event?.location?.venue);
  const source = fold(event?.source_name);
  const organizer = fold(event?.organizer);
  const candidates = [];

  for (const pattern of QUOTED_ACTIVITY) {
    pattern.lastIndex = 0;
    for (const match of description.matchAll(pattern)) {
      const candidate = cleanCandidate(match[1]);
      const normalized = fold(candidate);
      const words = normalized.split(/\s+/).filter(Boolean);
      if (!normalized || normalized === venue || normalized === source || normalized === organizer) continue;
      if (words.length < 2 || words.length > 16 || /https?:\/\/|www\./iu.test(candidate)) continue;

      const start = match.index || 0;
      const end = start + match[0].length;
      const after = description.slice(end, end + 80);
      const before = description.slice(Math.max(0, start - 70), start);
      const around = description.slice(Math.max(0, start - 120), end + 160);
      let score = 0;
      if (FOLLOWING_TITLE_VERBS.test(after)) score += 4;
      if (ACTIVITY_TERMS.test(around)) score += 2;
      if (/(?:exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla)\s*(?:titulada?|llamada?)?\s*$/iu.test(before)) score += 4;
      if (start <= 12) score += 1;
      if (words.length <= 10) score += 1;
      if (score >= 5) candidates.push({ candidate, score, start });
    }
  }

  candidates.sort((a, b) => b.score - a.score || a.start - b.start);
  return candidates[0]?.candidate || null;
}

function repairVenueTitle(event) {
  const recovered = recoverExplicitActivityTitle(event);
  if (!recovered) return event;

  const oldTitle = String(event?.title || "").trim();
  const editorial = {
    ...(event?.editorial || {}),
    title_original: event?.editorial?.title_original || oldTitle,
    title_recovered: true,
    title_recovery_reason: "explicit_quoted_activity_in_description",
  };
  let primaryCategory = event?.primary_category;
  let categories = event?.categories;
  const evidence = `${recovered} ${String(event?.description || "").slice(0, 500)}`;
  if (EXHIBITION_TERMS.test(evidence)) {
    primaryCategory = { id: "exposiciones", label: "Exposiciones" };
    categories = [primaryCategory];
    editorial.category_recovered_from_title_context = true;
  }

  return {
    ...event,
    title: recovered,
    primary_category: primaryCategory,
    categories,
    editorial,
  };
}

export function normalizeAgendaCategories(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const normalizedEvents = dataset.events.map((sourceEvent) => {
    const event = repairVenueTitle(sourceEvent);
    const category = resolvePublicCategory(event);
    return {
      ...event,
      primary_category: category,
      categories: [category],
    };
  });
  return {
    ...dataset,
    events: normalizeVenueAliases(normalizedEvents),
  };
}
