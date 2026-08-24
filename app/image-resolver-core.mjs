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

function escapeXml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function wrapGeneratedTitle(value, maxChars = 34, maxLines = 3) {
  const words = String(value || "Actividad cultural").replace(/\s+/g, " ").trim().split(" ");
  const lines = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length <= maxChars || !line) {
      line = candidate;
      continue;
    }
    lines.push(line);
    line = word;
    if (lines.length === maxLines - 1) break;
  }
  if (line && lines.length < maxLines) lines.push(line);
  const source = String(value || "").replace(/\s+/g, " ").trim();
  const joined = lines.join(" ");
  if (source.length > joined.length && lines.length) {
    lines[lines.length - 1] = `${lines[lines.length - 1].replace(/[.…]+$/u, "")}…`;
  }
  return lines;
}

export function safeHttpImageUrl(value, { baseUrl = null } = {}) {
  if (!value) return null;
  try {
    const text = String(value);
    let url;
    if (baseUrl && text.startsWith("./assets/event-images/")) {
      const base = new URL(baseUrl);
      const isAppSurface = /\/app(?:\/|$)/.test(base.pathname);
      url = new URL(isAppSurface ? text : `./app/${text.slice(2)}`, base);
    } else {
      url = baseUrl ? new URL(text, baseUrl) : new URL(text);
    }
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
  if (event?.image?.visual_quality === "text_heavy") return null;
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

export function generatedEventFallbackImage(event, hints = {}) {
  const category = categoryFallbackKey(event, hints);
  const categoryLabel = String(
    event?.primary_category?.label
      || event?.categories?.[0]?.label
      || hints?.labelHint
      || "Actividad cultural",
  ).trim();
  const title = String(event?.title || "Actividad cultural").replace(/\s+/g, " ").trim();
  const venue = String(event?.location?.venue || event?.location?.city || "").replace(/\s+/g, " ").trim();
  const lines = wrapGeneratedTitle(title);
  const titleSvg = lines.map((line, index) => (
    `<text x="64" y="${176 + index * 47}" font-family="Georgia,serif" font-size="34" font-weight="700" fill="#0b4b43">${escapeXml(line)}</text>`
  )).join("");
  const venueSvg = venue
    ? `<text x="64" y="362" font-family="Arial,sans-serif" font-size="20" fill="#5d6f6a">${escapeXml(venue.slice(0, 52))}</text>`
    : "";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="420" viewBox="0 0 720 420" role="img" aria-label="Imagen generada para ${escapeXml(title)}"><rect width="720" height="420" fill="#f7f4ec"/><rect x="0" y="0" width="720" height="12" fill="#ef8d3d"/><circle cx="642" cy="70" r="34" fill="#e5f0ec"/><text x="642" y="80" text-anchor="middle" font-family="Georgia,serif" font-size="31" fill="#0b4b43">✦</text><text x="64" y="92" font-family="Arial,sans-serif" font-size="18" font-weight="700" letter-spacing="1.6" fill="#9a552f">${escapeXml(categoryLabel.toUpperCase().slice(0, 46))}</text>${titleSvg}${venueSvg}<text x="64" y="397" font-family="Arial,sans-serif" font-size="14" fill="#7b8985">Imagen editorial generada · ${escapeXml(category)}</text></svg>`;
  return {
    url: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    kind: "generated-fallback",
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
    const direct = safeHttpImageUrl(event?.image?.url, { baseUrl });
    return direct
      ? { url: direct, kind: "relevant", genericSchedule: false }
      : { url: null, kind: "none", genericSchedule: false };
  }

  if (surface === "detail") {
    const direct = relevantEventImageUrl(event, { baseUrl });
    if (direct) return { url: direct, kind: "relevant", genericSchedule: false };
    return { ...categoryFallbackImage(event), genericSchedule: looksLikeGenericSchedule(event) };
  }

  const genericSchedule = looksLikeGenericSchedule(event);
  const direct = relevantEventImageUrl(event, { baseUrl });
  if (direct) return { url: direct, kind: "relevant", genericSchedule };

  const representative = representativeVenueImageUrl(event, venueImagePools);
  if (representative) return { url: representative, kind: "representative", genericSchedule };
  return { ...categoryFallbackImage(event), genericSchedule };
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
  return { ...categoryFallbackImage(event), genericSchedule: false };
}
