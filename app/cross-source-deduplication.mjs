const RECURRENCE_TITLE_TOKENS = new Set([
  "cada", "todos", "todas", "semanal", "semanales",
  "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "sabados", "domingo", "domingos",
]);
const TITLE_STOPWORDS = new Set([
  "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "e", "en", "para", "por", "con",
  "teatro", "obra", "funcion", "presentacion", "evento", "actividad", "espectaculo", "concierto", "show",
  ...RECURRENCE_TITLE_TOKENS,
]);
const VENUE_STOPWORDS = new Set(["de", "del", "la", "el", "los", "las", "y", "e", "ex"]);
const STRICT_START_TOLERANCE_MINUTES = 5;
const SCHEDULE_CONFLICT_TOLERANCE_MINUTES = 60;

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokens(value, stopwords = new Set()) {
  return fold(value).split(" ").filter((token) => token && !stopwords.has(token));
}

function unique(values) {
  return [...new Set((values || []).filter(Boolean))];
}

function localMinute(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!match) return null;
  return Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5])) / 60000;
}

function localDate(value) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/);
  return match ? match[1] : null;
}

function eventStarts(event) {
  const occurrences = Array.isArray(event?.schedule?.occurrences) ? event.schedule.occurrences : [];
  return occurrences.length ? occurrences.map((item) => item?.start).filter(Boolean) : [event?.schedule?.start].filter(Boolean);
}

function timedStarts(event) {
  return eventStarts(event).map(localMinute).filter(Number.isFinite);
}

function localDates(event) {
  return unique(eventStarts(event).map(localDate).filter(Boolean));
}

function sourceIdentity(event) {
  const sourceId = fold(event?.source_id);
  if (sourceId) return `id:${sourceId}`;
  const candidate = event?.source_url || event?.links?.source || event?.links?.official;
  if (candidate) {
    try { return `host:${new URL(String(candidate)).hostname.toLocaleLowerCase("en")}`; } catch {}
  }
  const label = fold(event?.source_name || event?.organizer);
  return label ? `label:${label}` : "";
}

function sameLocalStart(a, b, toleranceMinutes = STRICT_START_TOLERANCE_MINUTES) {
  const startsA = timedStarts(a);
  const startsB = timedStarts(b);
  if (!startsA.length || !startsB.length) return false;
  return startsA.some((left) => startsB.some((right) => Math.abs(left - right) <= toleranceMinutes));
}

function sameLocalDate(a, b) {
  const datesA = localDates(a);
  const datesB = new Set(localDates(b));
  return datesA.length > 0 && datesA.some((date) => datesB.has(date));
}

function minimumStartDifferenceMinutes(a, b) {
  const startsA = timedStarts(a);
  const startsB = timedStarts(b);
  if (!startsA.length || !startsB.length) return Number.POSITIVE_INFINITY;
  let minimum = Number.POSITIVE_INFINITY;
  for (const left of startsA) {
    for (const right of startsB) minimum = Math.min(minimum, Math.abs(left - right));
  }
  return minimum;
}

function titleCore(value) {
  return tokens(value, TITLE_STOPWORDS);
}

export function titleSimilarity(a, b) {
  const left = titleCore(a);
  const right = titleCore(b);
  if (!left.length || !right.length) return 0;
  const leftSet = new Set(left);
  const rightSet = new Set(right);
  const shared = [...leftSet].filter((token) => rightSet.has(token));
  const coverage = shared.length / Math.min(leftSet.size, rightSet.size);
  const union = new Set([...leftSet, ...rightSet]);
  const jaccard = shared.length / union.size;
  return Math.max(coverage, jaccard);
}

function titlesLikelySame(a, b) {
  const left = titleCore(a);
  const right = titleCore(b);
  if (!left.length || !right.length) return false;
  const leftText = left.join(" ");
  const rightText = right.join(" ");
  if (leftText === rightText) return true;

  const shorter = leftText.length <= rightText.length ? leftText : rightText;
  const longer = shorter === leftText ? rightText : leftText;
  if (shorter.length >= 7 && longer.includes(shorter)) return true;

  const leftSet = new Set(left);
  const rightSet = new Set(right);
  const shared = [...leftSet].filter((token) => rightSet.has(token));
  const minSize = Math.min(leftSet.size, rightSet.size);
  if (minSize === 1) return shared.length === 1 && shared[0].length >= 7;
  return shared.length >= 2 && shared.length / minSize >= 0.8;
}

function hasRecurrenceNoise(value) {
  return fold(value).split(" ").some((token) => RECURRENCE_TITLE_TOKENS.has(token));
}

function recurringTitlesLikelySame(a, b) {
  if (!(hasRecurrenceNoise(a) || hasRecurrenceNoise(b))) return false;
  const left = new Set(titleCore(a));
  const right = new Set(titleCore(b));
  if (!left.size || !right.size) return false;
  const shared = [...left].filter((token) => right.has(token));
  if (!shared.some((token) => token.length >= 4)) return false;
  return titleSimilarity(a, b) >= 0.75;
}

function cityKey(event) {
  return fold(event?.location?.city || event?.location?.commune);
}

function venueTokens(event) {
  const cityTokens = new Set(tokens(cityKey(event)));
  return tokens(event?.location?.venue, VENUE_STOPWORDS).filter((token) => !cityTokens.has(token));
}

function addressesLikelySame(a, b) {
  const left = fold(a?.location?.address);
  const right = fold(b?.location?.address);
  if (!(left && right)) return false;
  if (left === right) return true;
  const shorter = left.length <= right.length ? left : right;
  const longer = shorter === left ? right : left;
  return shorter.length >= 10 && longer.includes(shorter);
}

function venuesLikelySame(a, b) {
  const cityA = cityKey(a);
  const cityB = cityKey(b);
  if (cityA && cityB && cityA !== cityB) return false;
  if (addressesLikelySame(a, b)) return true;

  const rawA = fold(a?.location?.venue);
  const rawB = fold(b?.location?.venue);
  if (!(rawA && rawB)) return false;
  if (rawA === rawB) return true;
  const shorterRaw = rawA.length <= rawB.length ? rawA : rawB;
  const longerRaw = shorterRaw === rawA ? rawB : rawA;
  if (shorterRaw.length >= 8 && longerRaw.includes(shorterRaw)) return true;

  const left = new Set(venueTokens(a));
  const right = new Set(venueTokens(b));
  if (!left.size || !right.size) return false;
  const shared = [...left].filter((token) => right.has(token));
  const minSize = Math.min(left.size, right.size);
  if (minSize === 1) return shared.length === 1 && shared[0].length >= 5;
  return shared.length >= 2 && shared.length / minSize >= 0.8;
}

function hasOfficialSource(event) {
  return event?.public_status?.source_official === true;
}

function scheduleConflictDuplicate(a, b) {
  if (!(hasOfficialSource(a) || hasOfficialSource(b))) return false;
  if (!sameLocalDate(a, b)) return false;
  if (minimumStartDifferenceMinutes(a, b) > SCHEDULE_CONFLICT_TOLERANCE_MINUTES) return false;
  return recurringTitlesLikelySame(a?.title, b?.title);
}

function duplicateRule(a, b) {
  if (sameLocalStart(a, b) && titlesLikelySame(a?.title, b?.title)) return "same_time_similar_venue_similar_title";
  if (scheduleConflictDuplicate(a, b)) return "same_date_similar_venue_recurring_title_authoritative_source";
  return "cross_source_probable_duplicate";
}

function mergeObjectMissing(primary = {}, secondary = {}) {
  const output = { ...secondary, ...primary };
  for (const [key, value] of Object.entries(primary)) {
    if (value === null || value === undefined || value === "") output[key] = secondary[key] ?? value;
  }
  return output;
}

function mergeCategories(primary = [], secondary = []) {
  const found = new Map();
  for (const category of [...primary, ...secondary]) {
    const key = String(category?.id || fold(category?.label));
    if (key && !found.has(key)) found.set(key, category);
  }
  return [...found.values()];
}

function qualityScore(event) {
  let score = 0;
  if (hasOfficialSource(event)) score += 100;
  if (event?.public_status?.information_completeness === "complete") score += 20;
  if (event?.links?.official) score += 10;
  if (event?.image?.url) score += 6;
  if (event?.location?.address) score += 4;
  if (event?.public_status?.price_confirmed === true) score += 3;
  if (String(event?.description || "").length >= 80) score += 2;
  return score;
}

function priceAuthorityScore(event) {
  let score = 0;
  if (hasOfficialSource(event)) score += 100;
  if (event?.public_status?.price_confirmed === true) score += 20;
  const price = event?.price;
  if (price && typeof price === "object") {
    if (String(price.display_text || "").trim()) score += 5;
    if (price.is_free === true || price.is_free === false) score += 2;
    if (price.min_amount !== null && price.min_amount !== undefined) score += 1;
  }
  return score;
}

function selectPrice(primary, secondary) {
  const primaryScore = priceAuthorityScore(primary);
  const secondaryScore = priceAuthorityScore(secondary);
  if (primaryScore === 0 && secondaryScore === 0) return mergeObjectMissing(primary.price || {}, secondary.price || {});
  const chosen = secondaryScore > primaryScore ? secondary : primary;
  return chosen?.price ? { ...chosen.price } : {};
}

function editorialList(event, field, fallback) {
  const values = event?.editorial?.[field];
  return Array.isArray(values) && values.length ? values : fallback ? [fallback] : [];
}

export function areProbableDuplicateEvents(a, b) {
  if (!(a && b)) return false;
  const typeA = a.event_type || "event";
  const typeB = b.event_type || "event";
  if (["program", "flexible_offer"].includes(typeA) || ["program", "flexible_offer"].includes(typeB)) return false;
  if (typeA !== typeB) return false;

  const sourceA = sourceIdentity(a);
  const sourceB = sourceIdentity(b);
  if (!sourceA || !sourceB || sourceA === sourceB) return false;
  if (!venuesLikelySame(a, b)) return false;

  if (sameLocalStart(a, b) && titlesLikelySame(a?.title, b?.title)) return true;
  return scheduleConflictDuplicate(a, b);
}

export function mergeDuplicateEvents(a, b) {
  const primary = qualityScore(b) > qualityScore(a) ? b : a;
  const secondary = primary === a ? b : a;
  const primaryStatus = primary.public_status || {};
  const secondaryStatus = secondary.public_status || {};
  const publicStatus = mergeObjectMissing(primaryStatus, secondaryStatus);
  for (const field of ["registration_open", "registration_closed", "sold_out", "cancelled"]) {
    if (primaryStatus[field] === null || primaryStatus[field] === undefined) publicStatus[field] = secondaryStatus[field] ?? primaryStatus[field];
  }

  const mergedIds = unique([
    ...editorialList(primary, "merged_duplicate_ids", primary.id),
    ...editorialList(secondary, "merged_duplicate_ids", secondary.id),
  ]);
  const mergedSourceNames = unique([
    ...editorialList(primary, "merged_source_names", primary.source_name),
    ...editorialList(secondary, "merged_source_names", secondary.source_name),
  ]);
  const mergedSourceUrls = unique([
    ...editorialList(primary, "merged_source_urls", primary.source_url),
    ...editorialList(secondary, "merged_source_urls", secondary.source_url),
  ]);
  const mergedLocation = mergeObjectMissing(primary.location || {}, secondary.location || {});
  mergedLocation.venue_id = primary?.location?.venue_id ?? null;
  const rule = duplicateRule(primary, secondary);
  const scheduleConflictResolved = sameLocalDate(primary, secondary) && !sameLocalStart(primary, secondary);

  return {
    ...secondary,
    ...primary,
    source_id: primary.source_id ?? null,
    source_name: primary.source_name || primary.organizer || secondary.source_name || null,
    source_url: primary.source_url || primary?.links?.source || primary?.links?.official || secondary.source_url || null,
    organizer: primary.organizer ?? secondary.organizer ?? null,
    location: mergedLocation,
    price: selectPrice(primary, secondary),
    image: primary?.image?.url ? primary.image : secondary.image || primary.image,
    links: mergeObjectMissing(primary.links || {}, secondary.links || {}),
    categories: mergeCategories(primary.categories, secondary.categories),
    description: String(primary.description || "").trim() || secondary.description || primary.description,
    audience: primary.audience ?? secondary.audience ?? null,
    registration_requirements: primary.registration_requirements ?? secondary.registration_requirements ?? null,
    public_status: publicStatus,
    tags: unique([...(primary.tags || []), ...(secondary.tags || [])]),
    editorial: {
      ...(secondary.editorial || {}),
      ...(primary.editorial || {}),
      cross_source_deduplicated: true,
      deduplication_rule: rule,
      schedule_conflict_resolved: scheduleConflictResolved || undefined,
      merged_duplicate_ids: mergedIds,
      merged_source_names: mergedSourceNames,
      merged_source_urls: mergedSourceUrls,
    },
  };
}

export function deduplicateCrossSourceEvents(events) {
  if (!Array.isArray(events) || events.length < 2) return events;
  const output = [];
  for (const event of events) {
    const index = output.findIndex((candidate) => areProbableDuplicateEvents(candidate, event));
    if (index === -1) output.push(event);
    else output[index] = mergeDuplicateEvents(output[index], event);
  }
  return output;
}

function recalculateCounts(events, original = {}) {
  return {
    ...original,
    total: events.length,
    events: events.filter((event) => !["program", "flexible_offer", "course"].includes(event?.event_type)).length,
    courses: events.filter((event) => event?.event_type === "course").length,
    flexible_offers: events.filter((event) => event?.event_type === "flexible_offer").length,
    programs: events.filter((event) => event?.event_type === "program").length,
  };
}

export function deduplicateCrossSourceDataset(dataset) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  const events = deduplicateCrossSourceEvents(dataset.events);
  if (events.length === dataset.events.length && events.every((event, index) => event === dataset.events[index])) return dataset;
  return { ...dataset, events, counts: recalculateCounts(events, dataset.counts) };
}

export { fold, sameLocalStart, sameLocalDate, venuesLikelySame, titlesLikelySame };
