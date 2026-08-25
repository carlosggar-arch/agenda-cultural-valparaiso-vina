import {
  SCHEDULE_CONFLICT_TOLERANCE_MINUTES,
  minimumOccurrenceStartDifferenceMinutes,
  sameLocalOccurrenceDate,
  sameLocalOccurrenceStart,
} from "./occurrence-identity-core.mjs";

const RECURRENCE_TITLE_TOKENS = new Set([
  "cada", "todos", "todas", "semanal", "semanales",
  "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "sabados", "domingo", "domingos",
]);
const TITLE_STOPWORDS = new Set([
  "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "e", "en", "para", "por", "con",
  "teatro", "obra", "funcion", "presentacion", "evento", "actividad", "espectaculo", "concierto", "show",
  ...RECURRENCE_TITLE_TOKENS,
]);
const VENUE_STOPWORDS = new Set(["de", "del", "la", "el", "los", "las", "y", "e", "ex", "centro", "cultura", "primera", "planta"]);

export function foldEventIdentity(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokens(value, stopwords = new Set()) {
  return foldEventIdentity(value).split(" ").filter((token) => token && !stopwords.has(token));
}

function unique(values) {
  return [...new Set((values || []).filter(Boolean))];
}

function sourceIdentity(event) {
  const sourceId = foldEventIdentity(event?.source_id);
  if (sourceId) return `id:${sourceId}`;
  const candidate = event?.source_url || event?.links?.source || event?.links?.official;
  if (candidate) {
    try { return `host:${new URL(String(candidate)).hostname.toLocaleLowerCase("en")}`; } catch {}
  }
  const label = foldEventIdentity(event?.source_name || event?.organizer);
  return label ? `label:${label}` : "";
}

function normalizedSourceRecordUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(String(value));
    const path = url.pathname.replace(/\/+$/, "") || "/";
    return `${url.hostname.toLocaleLowerCase("en")}${path}`;
  } catch {
    return foldEventIdentity(value);
  }
}

function sourceRecordIdentity(event) {
  for (const candidate of [event?.source_url, event?.links?.source, event?.links?.official]) {
    const identity = normalizedSourceRecordUrl(candidate);
    if (identity) return identity;
  }
  return "";
}

function distinctSourceRecords(a, b) {
  const left = sourceRecordIdentity(a);
  const right = sourceRecordIdentity(b);
  return Boolean(left && right && left !== right);
}

function titleEchoedInOtherDescription(a, b) {
  const titleA = foldEventIdentity(a?.title);
  const titleB = foldEventIdentity(b?.title);
  const descriptionA = foldEventIdentity(a?.description);
  const descriptionB = foldEventIdentity(b?.description);
  return Boolean(
    (titleA.length >= 12 && descriptionB.includes(titleA))
    || (titleB.length >= 12 && descriptionA.includes(titleB))
  );
}

function urlHost(value) {
  if (!value) return "";
  try { return new URL(String(value)).hostname.toLocaleLowerCase("en"); } catch { return ""; }
}

function labelsLikelySame(a, b) {
  const left = foldEventIdentity(a);
  const right = foldEventIdentity(b);
  if (!(left && right)) return false;
  if (left === right) return true;
  const shorter = left.length <= right.length ? left : right;
  const longer = shorter === left ? right : left;
  return shorter.length >= 8 && longer.includes(shorter);
}

function hasDirectVenueSource(event) {
  if (!labelsLikelySame(event?.source_name, event?.location?.venue)) return false;
  const sourceHost = urlHost(event?.source_url || event?.links?.source);
  const officialHost = urlHost(event?.links?.official);
  return Boolean(sourceHost && officialHost && sourceHost === officialHost);
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

export function titlesLikelySame(a, b) {
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
  return foldEventIdentity(value).split(" ").some((token) => RECURRENCE_TITLE_TOKENS.has(token));
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
  return foldEventIdentity(event?.location?.city || event?.location?.commune);
}

function venueTokens(event) {
  const cityTokens = new Set(tokens(cityKey(event)));
  return tokens(event?.location?.venue, VENUE_STOPWORDS).filter((token) => !cityTokens.has(token));
}

function addressesLikelySame(a, b) {
  const left = foldEventIdentity(a?.location?.address);
  const right = foldEventIdentity(b?.location?.address);
  if (!(left && right)) return false;
  if (left === right) return true;
  const shorter = left.length <= right.length ? left : right;
  const longer = shorter === left ? right : left;
  return shorter.length >= 10 && longer.includes(shorter);
}

export function venuesLikelySame(a, b) {
  const venueIdA = foldEventIdentity(a?.location?.venue_id);
  const venueIdB = foldEventIdentity(b?.location?.venue_id);
  if (venueIdA && venueIdB && venueIdA === venueIdB) return true;
  const cityA = cityKey(a);
  const cityB = cityKey(b);
  if (cityA && cityB && cityA !== cityB) return false;
  if (addressesLikelySame(a, b)) return true;

  const rawA = foldEventIdentity(a?.location?.venue);
  const rawB = foldEventIdentity(b?.location?.venue);
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

function hasAuthoritativeSource(event) {
  return hasOfficialSource(event) || hasDirectVenueSource(event);
}

function scheduleDay(value) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})/u);
  return match?.[1] || "";
}

function dayDistance(left, right) {
  if (!(left && right)) return Number.POSITIVE_INFINITY;
  const a = Date.parse(`${left}T00:00:00Z`);
  const b = Date.parse(`${right}T00:00:00Z`);
  if (!(Number.isFinite(a) && Number.isFinite(b))) return Number.POSITIVE_INFINITY;
  return Math.abs(a - b) / 86400000;
}

function authoritativeMultiDayRangeDuplicate(a, b) {
  if (!(hasAuthoritativeSource(a) || hasAuthoritativeSource(b))) return false;
  if (!titlesLikelySame(a?.title, b?.title)) return false;
  const startA = scheduleDay(a?.schedule?.start);
  const startB = scheduleDay(b?.schedule?.start);
  const endA = scheduleDay(a?.schedule?.end);
  const endB = scheduleDay(b?.schedule?.end);
  if (!(startA && startB && endA && endB)) return false;
  // Long-running activities are sometimes published with the opening day in
  // one source and the first public-visit day in another. Reconcile only when
  // the closing boundary agrees exactly and the opening boundary differs by
  // at most one calendar day; venue and title identity are checked by the
  // caller before this rule can run.
  if (endA !== endB) return false;
  if (startA === endA || startB === endB) return false;
  return dayDistance(startA, startB) <= 1;
}

function scheduleConflictDuplicate(a, b) {
  if (!(hasAuthoritativeSource(a) || hasAuthoritativeSource(b))) return false;
  if (!sameLocalOccurrenceDate(a, b)) return false;
  if (minimumOccurrenceStartDifferenceMinutes(a, b) > SCHEDULE_CONFLICT_TOLERANCE_MINUTES) return false;
  return recurringTitlesLikelySame(a?.title, b?.title);
}

function duplicateRule(a, b) {
  if (sourceIdentity(a) === sourceIdentity(b) && distinctSourceRecords(a, b)) return "same_provider_distinct_record_duplicate";
  if (sameLocalOccurrenceStart(a, b) && titlesLikelySame(a?.title, b?.title)) return "same_time_similar_venue_similar_title";
  if (authoritativeMultiDayRangeDuplicate(a, b)) return "same_multiday_range_similar_venue_similar_title_authoritative_source";
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
    const key = String(category?.id || foldEventIdentity(category?.label));
    if (key && !found.has(key)) found.set(key, category);
  }
  return [...found.values()];
}

function qualityScore(event) {
  let score = 0;
  if (hasAuthoritativeSource(event)) score += 100;
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
  if (hasAuthoritativeSource(event)) score += 100;
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

function categoryEvidenceRecord(event) {
  const categoryId = String(
    event?.semantics?.primary_domain
      || event?.primary_category?.id
      || event?.categories?.[0]?.id
      || "",
  ).trim();
  if (!categoryId || categoryId === "unclassified") return null;
  const score = Number(event?.semantics?.score || 0);
  return {
    category_id: categoryId,
    confidence: String(event?.semantics?.confidence || "unspecified"),
    score: Number.isFinite(score) ? score : 0,
    event_id: String(event?.id || ""),
    source_id: String(event?.source_id || ""),
  };
}

function categoryEvidenceRecords(event) {
  const existing = event?.editorial?.merged_category_evidence;
  if (Array.isArray(existing) && existing.length) {
    return existing.filter((item) => item && typeof item === "object");
  }
  const record = categoryEvidenceRecord(event);
  return record ? [record] : [];
}

function mergeCategoryEvidence(primary, secondary) {
  const found = new Map();
  for (const item of [...categoryEvidenceRecords(primary), ...categoryEvidenceRecords(secondary)]) {
    const key = [item?.event_id, item?.source_id, item?.category_id].map((value) => String(value || "")).join("|");
    if (!item?.category_id || found.has(key)) continue;
    found.set(key, {
      category_id: String(item.category_id),
      confidence: String(item.confidence || "unspecified"),
      score: Number.isFinite(Number(item.score)) ? Number(item.score) : 0,
      event_id: String(item.event_id || ""),
      source_id: String(item.source_id || ""),
    });
  }
  return [...found.values()];
}

export function areProbableDuplicateEvents(a, b) {
  if (!(a && b)) return false;
  const typeA = a.event_type || "event";
  const typeB = b.event_type || "event";
  if (["program", "flexible_offer"].includes(typeA) || ["program", "flexible_offer"].includes(typeB)) return false;
  if (typeA !== typeB) return false;

  const sourceA = sourceIdentity(a);
  const sourceB = sourceIdentity(b);
  if (!sourceA || !sourceB) return false;
  const sameProviderDistinct = sourceA === sourceB && distinctSourceRecords(a, b);
  // A provider can publish the same activity twice through different records
  // (for example its official event page plus its Instagram post). Treat those
  // as independent evidence records eligible for reconciliation; exact repeats
  // of the very same source record remain outside this semantic rule.
  if (sourceA === sourceB && !sameProviderDistinct) return false;
  if (!venuesLikelySame(a, b)) return false;

  if (sameLocalOccurrenceStart(a, b)) {
    if (titlesLikelySame(a?.title, b?.title)) return true;
    // Same-provider publication titles are often editorially different (venue
    // listing vs social headline). A full title echoed in the other record's
    // description is stronger identity evidence than fuzzy title similarity.
    if (sameProviderDistinct && titleEchoedInOtherDescription(a, b)) return true;
  }
  if (authoritativeMultiDayRangeDuplicate(a, b)) return true;
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
  const scheduleConflictResolved = sameLocalOccurrenceDate(primary, secondary) && !sameLocalOccurrenceStart(primary, secondary);
  const mergedCategoryEvidence = mergeCategoryEvidence(primary, secondary);

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
      same_provider_reconciled: sourceIdentity(primary) === sourceIdentity(secondary) || undefined,
      deduplication_rule: rule,
      schedule_conflict_resolved: scheduleConflictResolved || undefined,
      merged_duplicate_ids: mergedIds,
      merged_source_names: mergedSourceNames,
      merged_source_urls: mergedSourceUrls,
      merged_category_evidence: mergedCategoryEvidence,
    },
  };
}
