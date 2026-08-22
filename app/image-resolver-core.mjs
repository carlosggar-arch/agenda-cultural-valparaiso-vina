const MONTH_PATTERN = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre";

export const CATEGORY_IMAGE_PATHS = Object.freeze({
  musica: "../assets/categoria-musica.jpg",
  cine: "../assets/categoria-cine.jpg",
  teatro: "../assets/categoria-teatro.jpg",
  exposiciones: "../assets/categoria-exposiciones.jpg",
  museos: "../assets/categoria-exposiciones.jpg",
  "cursos-talleres": "../assets/categoria-talleres.jpg",
  "cursos-talleres-campus": "../assets/categoria-talleres.jpg",
  deportes: "../assets/categoria-deportes.jpg",
  gastronomia: "../assets/categoria-gastronomia.jpg",
  ferias: "../assets/categoria-gastronomia.jpg",
  "naturaleza-montana": "../assets/categoria-naturaleza.jpg",
  cultura: "../assets/categoria-cultura.jpg",
});

const GENERIC_PROVIDER_HOSTS = /(^|\.)(passline\.com|eventrid\.cl|ticketplus\.(cl|com)|ticketmaster\.cl|puntoticket\.com|ticketpro\.(cl|com|net)|tickets\.cl|ticketera\.cl|ticketfacil\.cl|portaltickets\.cl|goignis\.cl)$/i;
const GENERIC_PROVIDER_PATH = /(?:^|\/)(?:assets?\/(?:img|images?)\/)?(?:icon|logo|favicon|placeholder|default|no[-_]?image|sin[-_]?imagen)(?:[-_.\/]|$)/i;
const GENERIC_AVATAR_HOSTS = /(^|\.)gravatar\.com$/i;

function foldWords(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function foldSlug(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function safeHttpImageUrl(value, { baseUrl = null } = {}) {
  if (!value) return null;
  try {
    const url = baseUrl ? new URL(String(value), baseUrl) : new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

export function rawHttpImageUrl(value) {
  const url = String(value || "").trim();
  return /^https?:\/\//i.test(url) ? url : null;
}

export function looksLikeGenericSchedule(event) {
  if (event?.image?.relevance === "generic_schedule") return true;
  const title = foldWords(event?.title);
  const description = foldWords(event?.description);
  if (/\b(agenda|cartelera|programacion|calendario|panoramas?)\b/.test(title)) return true;
  if (new RegExp(`^(?:destino|panoramas?) .+ (?:${MONTH_PATTERN}) 20\\d{2}$`).test(title)) return true;
  const mentions = (String(event?.description || "").match(/@[a-z0-9_.]+/gi) || []).length;
  return /\beste mes (?:tenemos|incluye|trae|hay)\b/.test(description) && mentions >= 2;
}

export function relevantEventImageUrl(event, { baseUrl = null } = {}) {
  if (looksLikeGenericSchedule(event)) return null;
  return safeHttpImageUrl(event?.image?.url, { baseUrl });
}

export function venueImageKey(event) {
  const city = foldWords(event?.location?.city);
  let venue = foldWords(event?.location?.venue);
  if (!city || !venue || venue === city || /^(?:online|sitio web)\b/.test(venue)) return null;
  if (venue.endsWith(` ${city}`)) venue = venue.slice(0, -(city.length + 1)).trim();
  return venue ? `${city}|${venue}` : null;
}

export function buildVenueImagePools(events, { baseUrl = null } = {}) {
  const pools = new Map();
  for (const event of events || []) {
    const key = venueImageKey(event);
    const url = relevantEventImageUrl(event, { baseUrl });
    if (!key || !url) continue;
    const pool = pools.get(key) || [];
    if (!pool.includes(url)) pool.push(url);
    pools.set(key, pool);
  }
  return pools;
}

export function representativeVenueImageUrl(event, venueImagePools) {
  if (looksLikeGenericSchedule(event)) return null;
  const key = venueImageKey(event);
  return key ? venueImagePools?.get(key)?.[0] || null : null;
}

export function categoryFallbackKey(event, { categoryHint = null, labelHint = null } = {}) {
  const runtimeCategory = event?.primary_category?.id || event?.categories?.[0]?.id;
  const explicit = foldSlug(runtimeCategory || categoryHint);
  if (explicit && CATEGORY_IMAGE_PATHS[explicit]) return explicit;

  const runtimeLabel = event?.primary_category?.label || event?.categories?.[0]?.label;
  const label = foldSlug(runtimeLabel || labelHint);
  if (/musica/.test(label)) return "musica";
  if (/cine/.test(label)) return "cine";
  if (/(teatro|artes-escenicas|danza)/.test(label)) return "teatro";
  if (/(exposicion|exposiciones|museo|museos|artes-visuales)/.test(label)) return "exposiciones";
  if (/(curso|cursos|taller|talleres|formacion)/.test(label)) return "cursos-talleres-campus";
  if (/(deporte|bienestar)/.test(label)) return "deportes";
  if (/(gastronomia|feria|ferias)/.test(label)) return "gastronomia";
  if (/(naturaleza|montana|caminata)/.test(label)) return "naturaleza-montana";
  return "cultura";
}

export function categoryFallbackImage(event, hints = {}) {
  const category = categoryFallbackKey(event, hints);
  return {
    url: CATEGORY_IMAGE_PATHS[category] || CATEGORY_IMAGE_PATHS.cultura,
    kind: "category-fallback",
    category,
  };
}

export function isGenericProviderImage(value, { baseUrl = null } = {}) {
  if (!value) return false;
  try {
    const url = baseUrl ? new URL(String(value), baseUrl) : new URL(String(value));
    const host = url.hostname.replace(/^www\./i, "");
    if (GENERIC_AVATAR_HOSTS.test(host)) return true;
    if (!GENERIC_PROVIDER_HOSTS.test(host)) return false;
    return GENERIC_PROVIDER_PATH.test(decodeURIComponent(url.pathname).toLocaleLowerCase("es"));
  } catch {
    return false;
  }
}

export function shouldInstallCategoryFallback({ placeholder = false, hasImage = true, currentUrl = null } = {}, { baseUrl = null } = {}) {
  return Boolean(placeholder || !hasImage || isGenericProviderImage(currentUrl, { baseUrl }));
}

export function resolveEventImage(event, {
  surface = "card",
  venueImagePools = null,
  baseUrl = null,
  allowDirect = true,
} = {}) {
  if (!allowDirect) return { url: null, kind: "none", genericSchedule: looksLikeGenericSchedule(event) };

  if (surface === "group") {
    const direct = rawHttpImageUrl(event?.image?.url);
    return direct
      ? { url: direct, kind: "relevant", genericSchedule: false }
      : { url: null, kind: "none", genericSchedule: false };
  }

  if (surface === "detail") {
    const direct = safeHttpImageUrl(event?.image?.url, { baseUrl });
    return direct
      ? { url: direct, kind: "relevant", genericSchedule: false }
      : { url: null, kind: "none", genericSchedule: false };
  }

  const genericSchedule = looksLikeGenericSchedule(event);
  const direct = relevantEventImageUrl(event, { baseUrl });
  if (direct) return { url: direct, kind: "relevant", genericSchedule };

  const representative = representativeVenueImageUrl(event, venueImagePools);
  if (representative) return { url: representative, kind: "representative", genericSchedule };
  return { url: null, kind: "none", genericSchedule };
}

export function resolveCardImageAfterFailure(event, failedUrl, {
  venueImagePools = null,
  baseUrl = null,
} = {}) {
  if (looksLikeGenericSchedule(event)) return { url: null, kind: "none", genericSchedule: true };
  const representative = representativeVenueImageUrl(event, venueImagePools);
  if (representative && representative !== failedUrl) {
    return { url: representative, kind: "representative", genericSchedule: false };
  }
  return { url: null, kind: "none", genericSchedule: false };
}
