const ANALYTICS_ENDPOINT = "https://agenda-cultural-community.carlosggar.workers.dev/community/v1/analytics/events";
const ALLOWED_EVENTS = new Set([
  "landing_view", "app_open", "event_open", "city_select", "filter_use", "search_use",
  "outbound_open", "calendar_download", "share", "app_install",
]);
const ALLOWED_FILTERS = new Set(["when", "area", "category", "city"]);
const sentViews = new Set();
const searchTimers = new WeakMap();

function cleanToken(value, limit = 80) {
  if (value === null || value === undefined) return "";
  return String(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9._:-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, limit);
}

function cleanEventId(value) {
  const text = String(value || "").trim();
  return /^[A-Za-z0-9._:-]{3,180}$/.test(text) ? text : "";
}

export function privacySignalEnabled() {
  return navigator.globalPrivacyControl === true
    || navigator.doNotTrack === "1"
    || window.doNotTrack === "1";
}

export function analyticsCity() {
  const explicit = document.documentElement.dataset.city || document.body?.dataset?.city;
  if (explicit && /^[a-z0-9][a-z0-9-]{0,63}$/.test(explicit)) return explicit;
  if (/\/evento\/gijon\//.test(location.pathname) || /\/gijon\/?$/.test(location.pathname)) return "gijon";
  return "valparaiso";
}

export function usageEvent(event, { city = analyticsCity(), dimension = "", value = "", eventId = "" } = {}) {
  if (!ALLOWED_EVENTS.has(event)) return null;
  const safeCity = cleanToken(city, 64);
  if (!safeCity) return null;
  const item = { event, city: safeCity };
  const safeDimension = cleanToken(dimension, 30);
  const safeValue = cleanToken(value, 80);
  const safeEventId = cleanEventId(eventId);
  if (safeDimension) item.dimension = safeDimension;
  if (safeValue) item.value = safeValue;
  if (safeEventId) item.event_id = safeEventId;
  return item;
}

export function trackUsage(event, details = {}) {
  if (privacySignalEnabled()) return false;
  const item = usageEvent(event, details);
  if (!item) return false;
  try {
    fetch(ANALYTICS_ENDPOINT, {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      keepalive: true,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ events: [item] }),
    }).catch(() => {});
    return true;
  } catch {
    return false;
  }
}

function isEventPage() {
  return document.body?.dataset?.eventPage !== undefined;
}

function isAppSurface() {
  return /\/app\/?$/.test(location.pathname) || location.pathname.includes("/app/");
}

function trackSurfaceView() {
  if (isEventPage()) return;
  const city = analyticsCity();
  const event = isAppSurface() ? "app_open" : "landing_view";
  const key = `${event}:${city}`;
  if (sentViews.has(key)) return;
  sentViews.add(key);
  trackUsage(event, { city, dimension: "surface", value: isAppSurface() ? "app" : "web" });
}

function eventContext(node) {
  const card = node?.closest?.("[data-event-id]");
  const eventId = cleanEventId(node?.dataset?.openEvent || card?.dataset?.eventId || document.body?.dataset?.eventId);
  return { city: analyticsCity(), eventId };
}

function classifyOutbound(node) {
  const text = `${node.textContent || ""} ${node.className || ""}`.toLocaleLowerCase("es");
  if (/entrada|ticket/.test(text)) return "tickets";
  if (/inscri|reserv/.test(text)) return "registration";
  if (/open data/.test(text)) return "open-data";
  if (/fuente oficial/.test(text)) return "official";
  if (/fuente|referencia/.test(text)) return "source";
  return "external";
}

function filterFromNode(node) {
  if (node.matches?.("[data-section-filter]")) return ["when", node.dataset.sectionFilter || "all"];
  if (node.matches?.("[data-category-filter]")) return ["category", node.dataset.categoryFilter || "all"];
  if (node.matches?.("[data-city-option]")) return ["city", node.dataset.cityOption || "unknown"];
  if (node.matches?.("[data-filter-value]")) {
    const owner = node.closest("[data-combined-when],[data-combined-area],[data-combined-category-filters]");
    const dimension = owner?.hasAttribute("data-combined-when") ? "when"
      : owner?.hasAttribute("data-combined-area") ? "area"
        : owner?.hasAttribute("data-combined-category-filters") ? "category" : null;
    return dimension ? [dimension, node.dataset.filterValue || "all"] : null;
  }
  return null;
}

function trackFilter(dimension, value) {
  if (!ALLOWED_FILTERS.has(dimension)) return;
  trackUsage("filter_use", { dimension, value });
}

function onClick(event) {
  const node = event.target.closest?.("button,a");
  if (!node) return;

  const filter = filterFromNode(node);
  if (filter) {
    if (node.matches("[data-city-option]")) {
      trackUsage("city_select", { city: filter[1], dimension: "city", value: filter[1] });
    } else {
      trackFilter(filter[0], filter[1]);
    }
  }

  if (node.matches("[data-open-event]")) {
    const context = eventContext(node);
    trackUsage("event_open", { city: context.city, eventId: context.eventId });
  }

  if (node.matches("[data-native-share],[data-copy-link]") || /^compartir$/i.test(String(node.textContent || "").trim())) {
    const context = eventContext(node);
    trackUsage("share", { city: context.city, dimension: "action", value: "share", eventId: context.eventId });
  }

  if (node.tagName === "A") {
    let url = null;
    try { url = new URL(node.href, location.href); } catch {}
    const context = eventContext(node);
    if (url?.pathname.endsWith("evento.ics")) {
      trackUsage("calendar_download", { city: context.city, dimension: "action", value: "calendar", eventId: context.eventId });
    } else if (url && url.origin !== location.origin) {
      trackUsage("outbound_open", { city: context.city, dimension: "action", value: classifyOutbound(node), eventId: context.eventId });
    }
  }
}

function onChange(event) {
  const node = event.target;
  const mappings = [
    ["[data-filter-city]", "city"], ["[data-top-city]", "city"],
    ["[data-filter-category]", "category"], ["[data-top-category]", "category"],
    ["[data-filter-period]", "when"],
  ];
  for (const [selector, dimension] of mappings) {
    if (!node.matches?.(selector)) continue;
    trackFilter(dimension, node.value || "all");
    return;
  }
}

function searchLengthBucket(length) {
  if (length < 2) return null;
  if (length <= 4) return "2-4";
  if (length <= 9) return "5-9";
  return "10plus";
}

function onSearchInput(event) {
  const input = event.target;
  if (!input.matches?.('input[type="search"], [data-smart-search], [data-filter-query], [data-header-query], [data-mobile-query]')) return;
  clearTimeout(searchTimers.get(input));
  const bucket = searchLengthBucket(String(input.value || "").trim().length);
  if (!bucket) return;
  searchTimers.set(input, setTimeout(() => {
    trackUsage("search_use", { dimension: "search_length", value: bucket });
  }, 800));
}

function trackPermanentEventPage() {
  if (!isEventPage()) return;
  trackUsage("event_open", { eventId: document.body.dataset.eventId });
}

document.addEventListener("click", onClick, true);
document.addEventListener("change", onChange, true);
document.addEventListener("input", onSearchInput, true);
window.addEventListener("appinstalled", () => trackUsage("app_install", { dimension: "action", value: "installed" }), { once: true });
new MutationObserver(trackSurfaceView).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

trackSurfaceView();
trackPermanentEventPage();

export const ANALYTICS_PRIVACY = Object.freeze({
  cookies: false,
  identifiers: false,
  rawSearchQueries: false,
  coordinates: false,
  rawUrls: false,
  thirdPartyAnalytics: false,
  honorsGlobalPrivacyControl: true,
  honorsDoNotTrack: true,
});
