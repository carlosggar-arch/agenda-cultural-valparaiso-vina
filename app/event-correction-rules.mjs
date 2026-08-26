function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const GENERIC_PROMOTIONAL_TITLE_PATTERNS = Object.freeze([
  /^entradas?\s+a\s+la\s+venta(?:\b|$)/u,
  /^venta\s+de\s+entradas?(?:\b|$)/u,
  /^consulta(?:r)?\s+(?:horarios?|precio|precios|informaci[oó]n)(?:\b|$)/u,
  /^m[aá]s\s+informaci[oó]n(?:\b|$)/u,
  /^informaci[oó]n\s+y\s+entradas?(?:\b|$)/u,
]);

export const PUBLIC_EVENT_CORRECTION_RULES = Object.freeze([
  Object.freeze({
    id: "official-program-category-los-fantasmas",
    cityId: "valparaiso",
    match: Object.freeze({ eventId: "agenda_bc147abef119a17edb8a9770" }),
    ensureCategories: Object.freeze([Object.freeze({ id: "teatro", label: "Teatro" })]),
    authority: "official_program",
  }),
  Object.freeze({
    id: "gijon-acapulco-anime-official-poster-title",
    cityId: "gijon",
    match: Object.freeze({ eventId: "gijon_sala_acapulco_conciertos_b7ba72ea73050459" }),
    replaceTitle: "La Mejor Fiesta Anime",
    authority: "official_poster",
  }),
  Object.freeze({
    id: "gijon-jazz-xixon-recital-title-capitalization",
    cityId: "gijon",
    match: Object.freeze({
      titleFolded: "daniel garcia diego pablo martin caminero recital 2 0 jazz xixon",
    }),
    replaceTitle: "Daniel García Diego - Pablo Martín Caminero. Recital 2.0 | Jazz Xixón",
    authority: "official_program_editorial_title",
  }),
]);

export function isGenericPromotionalTitle(value) {
  const normalized = fold(value);
  return Boolean(normalized && GENERIC_PROMOTIONAL_TITLE_PATTERNS.some((pattern) => pattern.test(normalized)));
}

function matchesRule(event, rule, cityId) {
  if (rule?.cityId && String(rule.cityId) !== String(cityId || "")) return false;
  if (rule?.match?.eventId && String(event?.id || "") !== String(rule.match.eventId)) return false;
  if (rule?.match?.sourceId && String(event?.source_id || "") !== String(rule.match.sourceId)) return false;
  if (rule?.match?.titleFolded && fold(event?.title) !== fold(rule.match.titleFolded)) return false;
  return true;
}

function applyRule(event, rule) {
  const categories = Array.isArray(event?.categories) ? [...event.categories] : [];
  let changed = false;
  for (const category of rule.ensureCategories || []) {
    if (categories.some((candidate) => candidate?.id === category.id)) continue;
    categories.push({ ...category });
    changed = true;
  }

  let title = event?.title;
  let image = event?.image;
  if (rule.replaceTitle && String(rule.replaceTitle) !== String(event?.title || "")) {
    const originalTitle = String(event?.title || "").trim();
    title = String(rule.replaceTitle);
    const currentImage = event?.image && typeof event.image === "object" ? event.image : null;
    if (currentImage && fold(currentImage.alt) === fold(originalTitle)) {
      image = { ...currentImage, alt: title };
    }
    changed = true;
  }

  if (!changed) return event;
  const appliedRules = new Set([...(event?.editorial?.applied_correction_rules || []), rule.id]);
  return {
    ...event,
    ...(title !== event?.title ? { title } : {}),
    ...(image !== event?.image ? { image } : {}),
    ...(categories !== event?.categories ? { categories } : {}),
    editorial: {
      ...(event?.editorial || {}),
      ...(rule.replaceTitle && event?.title !== title && !event?.editorial?.title_original
        ? { title_original: event?.title }
        : {}),
      applied_correction_rules: [...appliedRules],
      correction_authority: rule.authority || "declared_rule",
    },
  };
}

export function applyDeclarativeEventCorrectionRules(dataset, {
  cityId = "",
  rules = PUBLIC_EVENT_CORRECTION_RULES,
} = {}) {
  if (!dataset || !Array.isArray(dataset.events)) return dataset;
  let changed = false;
  const events = [];
  for (const event of dataset.events) {
    let corrected = event;
    for (const rule of rules) {
      if (matchesRule(corrected, rule, cityId)) corrected = applyRule(corrected, rule);
    }

    // A CTA or sales instruction is not an event title. If a source emits one
    // and no explicit evidence-based correction recovered the real title, do
    // not let the malformed card reach the public renderer.
    if (isGenericPromotionalTitle(corrected?.title)) {
      changed = true;
      continue;
    }

    if (corrected !== event) changed = true;
    events.push(corrected);
  }
  return changed ? { ...dataset, events } : dataset;
}
