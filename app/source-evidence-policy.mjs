const SOURCE_PRIORITY = Object.freeze({
  official: 0,
  institutional: 1,
  ticketing: 2,
  web: 3,
  social_aggregator: 4,
});

const SOCIAL_HOSTS = new Set([
  "instagram.com", "facebook.com", "fb.com", "tiktok.com", "x.com",
  "twitter.com", "youtube.com", "youtu.be", "threads.net",
]);
const TICKETING_TOKENS = [
  "ticketmaster", "ticketplus", "puntoticket", "passline", "portaldisc",
  "portaltickets", "entradium", "eventbrite", "ticketrona", "ticketmundo",
  "ticketpro", "tickantel", "atrapalo",
];
const INSTITUTIONAL_TOKENS = [
  ".gob.", ".gov.", ".edu.", ".ac.", "municipal", "muni",
  "gijon.es", "asturias.es", "cultura.gob", "cultura.gijon",
];
const AGGREGATOR_TOKENS = ["panorama", "agenda", "cartelera", "allevents", "songkick", "bandsintown"];
const TRACKING_KEYS = new Set(["fbclid", "gclid", "igsh", "mc_cid", "mc_eid", "ref_src"]);
const EXPLICIT_KINDS = Object.freeze({
  official: "official",
  official_venue: "official",
  official_organizer: "official",
  venue: "official",
  organizer: "official",
  institutional: "institutional",
  government: "institutional",
  municipal: "institutional",
  university: "institutional",
  ticketing: "ticketing",
  ticketera: "ticketing",
  tickets: "ticketing",
  web: "web",
  website: "web",
  social: "social_aggregator",
  social_media: "social_aggregator",
  aggregator: "social_aggregator",
});

function clean(value) {
  return String(value || "").replace(/\s+/gu, " ").trim();
}

function fold(value) {
  return clean(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/gu, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/gu, " ")
    .trim();
}

function labelsSame(a, b) {
  const left = fold(a);
  const right = fold(b);
  if (!(left && right)) return false;
  if (left === right) return true;
  const [shorter, longer] = [left, right].sort((x, y) => x.length - y.length);
  return shorter.length >= 8 && longer.startsWith(shorter);
}

export function normalizeSourceUrl(value) {
  const text = clean(value);
  if (!text) return null;
  let url;
  try {
    url = new URL(text);
  } catch {
    return null;
  }
  if (!["http:", "https:"].includes(url.protocol)) return null;
  url.protocol = url.protocol.toLocaleLowerCase("en");
  url.hostname = url.hostname.toLocaleLowerCase("en").replace(/^www\./u, "");
  url.hash = "";
  for (const key of [...url.searchParams.keys()]) {
    const lower = key.toLocaleLowerCase("en");
    if (lower.startsWith("utm_") || TRACKING_KEYS.has(lower)) url.searchParams.delete(key);
  }
  if (url.pathname !== "/") url.pathname = url.pathname.replace(/\/+$/u, "");
  return url.href.replace(/\/$/u, "");
}

function host(value) {
  try {
    return new URL(String(value || "")).hostname.toLocaleLowerCase("en").replace(/^www\./u, "");
  } catch {
    return "";
  }
}

function explicitKind(event) {
  const values = [event?.source_kind, event?.source_type, event?.source_role, event?.source?.kind];
  for (const value of values) {
    const key = fold(value).replace(/\s+/gu, "_");
    if (EXPLICIT_KINDS[key]) return EXPLICIT_KINDS[key];
  }
  return null;
}

function ownerName(event) {
  return clean(event?.source_name || event?.organizer || event?.account) || null;
}

function directOwnerSource(event) {
  const sourceName = ownerName(event);
  const venue = event?.location?.venue || event?.venue;
  const organizer = event?.organizer;
  if (sourceName && (labelsSame(sourceName, venue) || labelsSame(sourceName, organizer))) return true;
  return event?.public_status?.source_official === true;
}

export function classifySourceEvidence(event, value, role = "source") {
  const url = normalizeSourceUrl(value);
  const explicit = explicitKind(event);
  const sourceHost = host(url);

  if (role === "source" && (explicit === "official" || directOwnerSource(event))) {
    return { source_kind: "official", rank: 0, confidence_rank: 0 };
  }
  if (role === "official") {
    return {
      source_kind: "official",
      rank: 0,
      confidence_rank: explicit === "official" || directOwnerSource(event) ? 0 : 1,
    };
  }
  if (explicit && role === "source") {
    return { source_kind: explicit, rank: SOURCE_PRIORITY[explicit], confidence_rank: 0 };
  }
  if (role === "tickets") return { source_kind: "ticketing", rank: 2, confidence_rank: 0 };

  if (INSTITUTIONAL_TOKENS.some((token) => sourceHost.includes(token))) {
    return { source_kind: "institutional", rank: 1, confidence_rank: 1 };
  }
  if (TICKETING_TOKENS.some((token) => sourceHost.includes(token))) {
    return { source_kind: "ticketing", rank: 2, confidence_rank: 1 };
  }
  if (SOCIAL_HOSTS.has(sourceHost) || [...SOCIAL_HOSTS].some((item) => sourceHost.endsWith(`.${item}`))) {
    return { source_kind: "social_aggregator", rank: 4, confidence_rank: 1 };
  }

  const label = fold(ownerName(event));
  if (/(municipalidad|ministerio|universidad|instituto|gobierno)/u.test(label)) {
    return { source_kind: "institutional", rank: 1, confidence_rank: 2 };
  }
  if (/(ticket|entradas|passline|puntoticket)/u.test(label)) {
    return { source_kind: "ticketing", rank: 2, confidence_rank: 2 };
  }
  if (/(instagram|facebook|panorama|agenda|cartelera)/u.test(label)
      || AGGREGATOR_TOKENS.some((token) => sourceHost.includes(token))) {
    return { source_kind: "social_aggregator", rank: 4, confidence_rank: 2 };
  }
  if (url) return { source_kind: "web", rank: 3, confidence_rank: 3 };
  return { source_kind: "social_aggregator", rank: 4, confidence_rank: 4 };
}

function evidenceCandidate(event, rawUrl, role) {
  const url = normalizeSourceUrl(rawUrl);
  if (!url) return null;
  const classification = classifySourceEvidence(event, url, role);
  const sourceName = role === "official"
    ? clean(event?.organizer || event?.location?.venue || event?.source_name) || null
    : ownerName(event);
  return {
    url,
    ...classification,
    source_id: clean(event?.source_id) || null,
    source_name: sourceName,
  };
}

export function eventSourceEvidence(event) {
  if (!event || typeof event !== "object") return [];
  const links = event.links && typeof event.links === "object" ? event.links : {};
  const items = [];
  const add = (value, role) => {
    const candidate = evidenceCandidate(event, value, role);
    if (candidate) items.push(candidate);
  };

  add(event.source_url || event.url || links.source, "source");
  add(links.official, "official");
  add(links.tickets, "tickets");
  for (const value of event.secondary_source_urls || []) add(value, "secondary");
  for (const value of event?.editorial?.merged_source_urls || []) add(value, "secondary");

  const byUrl = new Map();
  for (const item of items) {
    const current = byUrl.get(item.url);
    if (!current
        || item.rank < current.rank
        || (item.rank === current.rank && item.confidence_rank < current.confidence_rank)) {
      byUrl.set(item.url, item);
    }
  }
  return [...byUrl.values()];
}

function evidenceOrder(a, b) {
  return a.rank - b.rank
    || a.confidence_rank - b.confidence_rank
    || a.url.localeCompare(b.url, "en");
}

export function chooseCanonicalSourceEvidence(...events) {
  const byUrl = new Map();
  for (const event of events) {
    for (const item of eventSourceEvidence(event)) {
      const current = byUrl.get(item.url);
      if (!current || evidenceOrder(item, current) < 0) byUrl.set(item.url, item);
    }
  }
  const ordered = [...byUrl.values()].sort(evidenceOrder);
  return {
    primary: ordered[0] || null,
    secondary: ordered.slice(1),
  };
}

export function applyCanonicalSourceEvidence(event, ...evidenceEvents) {
  const result = { ...(event || {}) };
  const { primary, secondary } = chooseCanonicalSourceEvidence(result, ...evidenceEvents);
  if (!primary) {
    if (!Array.isArray(result.secondary_source_urls)) result.secondary_source_urls = [];
    return result;
  }

  const links = { ...(result.links || {}), source: primary.url };
  return {
    ...result,
    source_id: primary.source_id || result.source_id || null,
    source_name: primary.source_name || result.source_name || result.organizer || null,
    source_url: primary.url,
    secondary_source_urls: secondary.map((item) => item.url),
    links,
  };
}

export { SOURCE_PRIORITY };
