import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const STYLE_ID = "agenda-presentation-normalizer";
const CITY_REGISTRY = await loadCityRegistry();
const CITIES = CITY_REGISTRY.byId;

const KNOWN_ACRONYMS = Object.freeze([
  "AI", "DJ", "DJS", "IA", "LGBT", "LGBTQ", "MNHN", "ONU", "PUCV",
  "SIDA", "UAI", "UNESCO", "USM", "UTFSM", "UV", "VIH",
]);

const OUTER_QUOTES = Object.freeze([
  ['"', '"'],
  ['“', '”'],
  ['‘', '’'],
  ["'", "'"],
  ['«', '»'],
  ['‹', '›'],
]);

// Only remove generic activity words when they are clearly acting as a label,
// e.g. "Obra: Noche de Reyes" or "Obra “Noche de Reyes”". We deliberately
// do not remove them from genuine names such as "Concierto para piano".
const GENERIC_TITLE_PREFIX = /^(?:obra(?:\s+de\s+teatro)?|concierto|recital|exposici[oó]n|exhibici[oó]n|muestra|charla|taller|curso|funci[oó]n)\s*(?:(?:[:\-–—]\s*)|(?=["“‘'«‹]))/iu;

let loadedCity = null;
let loadingCity = null;
let eventsById = new Map();
let queued = false;

function installStyles() {
  let style = document.getElementById(STYLE_ID);
  if (!style) {
    style = document.createElement("style");
    style.id = STYLE_ID;
    document.head.append(style);
  }
  style.textContent = `
    /* One category component for normal and grouped cards. */
    .event-grid .exhibition-venue-body {
      display: flex !important;
      flex-direction: column !important;
      gap: .56rem !important;
      padding: .84rem .92rem .92rem !important;
    }

    .event-grid .exhibition-venue-meta {
      box-sizing: border-box !important;
      display: flex !important;
      align-items: flex-start !important;
      min-height: 1.6rem !important;
      margin: 0 !important;
      padding: 0 !important;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
      font-size: .78rem !important;
      font-weight: 800 !important;
      line-height: normal !important;
      letter-spacing: .08em !important;
      text-transform: uppercase !important;
      color: #8d5a3b !important;
    }

    html[data-city="valparaiso"] .event-grid .exhibition-venue-meta,
    html[data-city="valparaiso"] .event-card .meta {
      color: #a9562f !important;
    }

    .event-grid .exhibition-venue-heading {
      margin: 0 !important;
    }

    .event-grid .exhibition-venue-facts {
      margin-top: 0 !important;
    }

    .event-grid .event-card-body > .card-meta-row,
    .event-grid .exhibition-venue-meta {
      min-height: 1.6rem !important;
    }

    @media (max-width: 560px) {
      .event-grid .exhibition-venue-body {
        gap: .52rem !important;
        padding: .78rem .84rem .84rem !important;
      }
    }
  `;
}

function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function flexibleLiteral(value) {
  return escapeRegExp(String(value || "").trim()).replace(/\\\s+/g, "\\s+");
}

function stripOuterQuotes(value) {
  let text = value.trim();
  let changed = true;
  while (changed && text.length > 1) {
    changed = false;
    for (const [open, close] of OUTER_QUOTES) {
      if (text.startsWith(open) && text.endsWith(close)) {
        text = text.slice(open.length, -close.length).trim();
        changed = true;
        break;
      }
    }
  }
  return text;
}

function stripTerminalPeriod(value) {
  const text = value.trim();
  if (text.endsWith(".") && !text.endsWith("...")) return text.slice(0, -1).trim();
  return text;
}

function stripGenericPrefix(value) {
  return value.replace(GENERIC_TITLE_PREFIX, "").trim();
}

function stripKnownLocationSuffix(value, event) {
  let text = value.trim();
  const venue = String(event?.location?.venue || "").trim();
  const city = String(event?.location?.city || "").trim();
  if (!venue && !city) return text;

  const venueRx = venue ? flexibleLiteral(venue) : null;
  const cityRx = city ? flexibleLiteral(city) : null;
  const separator = "\\s*[,·|/\\-–—]\\s*";
  const patterns = [];

  if (venueRx && cityRx) {
    patterns.push(new RegExp(`\\s+(?:en|@)\\s+${venueRx}(?:${separator}${cityRx})?\\s*$`, "iu"));
    patterns.push(new RegExp(`${separator}${venueRx}(?:${separator}${cityRx})?\\s*$`, "iu"));
    patterns.push(new RegExp(`\\s+${venueRx}${separator}${cityRx}\\s*$`, "iu"));
  }
  if (venueRx) {
    patterns.push(new RegExp(`\\s+(?:en|@)\\s+${venueRx}\\s*$`, "iu"));
    patterns.push(new RegExp(`${separator}${venueRx}\\s*$`, "iu"));
  }
  if (cityRx) {
    patterns.push(new RegExp(`${separator}${cityRx}\\s*$`, "iu"));
  }

  // A title may contain both venue and city; remove the longest suffix first and
  // repeat once so "... en Venue, City" cannot leave a dangling location fragment.
  for (let pass = 0; pass < 2; pass += 1) {
    const before = text;
    for (const pattern of patterns) {
      const candidate = text.replace(pattern, "").trim();
      if (candidate && candidate !== text) {
        text = candidate;
        break;
      }
    }
    if (text === before) break;
  }
  return text;
}

function isAllCapsTitle(value) {
  const letters = [...value].filter((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  return letters.length >= 5 && letters.every((char) => char === char.toLocaleUpperCase("es"));
}

function restoreKnownAcronyms(value) {
  let text = value;
  for (const acronym of KNOWN_ACRONYMS) {
    const escaped = escapeRegExp(acronym);
    text = text.replace(new RegExp(`\\b${escaped.toLocaleLowerCase("es")}\\b`, "giu"), acronym);
  }
  return text;
}

function sentenceCase(value) {
  let text = value.toLocaleLowerCase("es");
  text = restoreKnownAcronyms(text);
  const index = [...text].findIndex((char) => char.toLocaleLowerCase("es") !== char.toLocaleUpperCase("es"));
  if (index < 0) return text;
  const chars = [...text];
  chars[index] = chars[index].toLocaleUpperCase("es");
  return chars.join("");
}

export function normalizeDisplayTitle(value, event = null) {
  let text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return text;

  // Normalize only public presentation; source data remains unchanged.
  for (let index = 0; index < 2; index += 1) {
    text = stripTerminalPeriod(text);
    text = stripOuterQuotes(text);
  }

  text = stripGenericPrefix(text);
  text = stripOuterQuotes(text);
  if (event) text = stripKnownLocationSuffix(text, event);

  for (let index = 0; index < 2; index += 1) {
    text = stripTerminalPeriod(text);
    text = stripOuterQuotes(text);
  }

  if (isAllCapsTitle(text)) text = sentenceCase(text);
  return text.trim();
}

function currentCityId() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return CITIES[id] ? id : null;
}

async function ensureEventIndex() {
  const cityId = currentCityId();
  if (!cityId) return;
  if (loadedCity === cityId && eventsById.size) return;
  if (loadingCity === cityId) return;

  loadingCity = cityId;
  try {
    const response = await fetch(CITIES[cityId].dataset, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) return;
    const dataset = await response.json();
    if (currentCityId() !== cityId || !Array.isArray(dataset.events)) return;
    eventsById = new Map(dataset.events
      .map((event) => [String(event?.id || "").trim(), event])
      .filter(([id]) => id));
    loadedCity = cityId;
  } catch {
    eventsById = new Map();
  } finally {
    if (loadingCity === cityId) loadingCity = null;
  }
}

function eventIdForNode(node) {
  const grouped = node.closest("[data-grouped-event-id]");
  if (grouped?.dataset.groupedEventId) return grouped.dataset.groupedEventId;

  const card = node.closest(".event-card[data-event-id]");
  if (card?.dataset.eventId) return card.dataset.eventId;

  const detail = node.closest("[data-event-detail]");
  if (detail?.dataset.eventDetail) return detail.dataset.eventDetail;
  return null;
}

function normalizeNode(node) {
  if (!(node instanceof HTMLElement)) return;
  const original = node.dataset.originalPublicTitle || node.textContent || "";
  if (!node.dataset.originalPublicTitle) node.dataset.originalPublicTitle = original;
  const event = eventsById.get(String(eventIdForNode(node) || "").trim()) || null;
  const normalized = normalizeDisplayTitle(original, event);
  if (normalized && node.textContent !== normalized) node.textContent = normalized;
}

function normalizeVisibleTitles(root = document) {
  const selectors = [
    '.event-card[data-event-id] .event-card-body h4',
    '.event-card[data-event-id]:not(.exhibition-venue-card) > h4',
    '.grouped-exhibition-copy strong',
    '.event-detail-title',
  ];
  for (const node of root.querySelectorAll(selectors.join(','))) normalizeNode(node);
}

function queueNormalize() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(async () => {
    queued = false;
    await ensureEventIndex();
    normalizeVisibleTitles();
  });
}

installStyles();
queueNormalize();

new MutationObserver(queueNormalize).observe(document.body, {
  childList: true,
  subtree: true,
  characterData: true,
});

new MutationObserver(() => {
  loadedCity = null;
  loadingCity = null;
  eventsById = new Map();
  queueNormalize();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
