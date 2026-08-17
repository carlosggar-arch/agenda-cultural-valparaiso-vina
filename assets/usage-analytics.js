const ANALYTICS_ENDPOINT = "https://agenda-cultural-community.carlosggar.workers.dev/api/community/v1/analytics/events";
const ALLOWED_EVENTS = new Set(["app_open", "event_open", "search", "filter_apply", "outbound_open", "share", "calendar_download", "install"]);
const LIMITS = Object.freeze({ category: 80, eventId: 160, filter: 40, value: 80, target: 40 });
const sentAppOpens = new Set();
const searchTimers = new WeakMap();

function clean(value, limit) {
  if (value === null || value === undefined) return null;
  const text = String(value).replace(/\s+/g, " ").trim();
  return text ? text.slice(0, limit) : null;
}

export function analyticsCity() {
  const explicit = document.documentElement.dataset.city || document.body?.dataset?.city;
  if (explicit === "gijon" || explicit === "valparaiso") return explicit;
  if (/\/evento\/gijon\//.test(location.pathname) || /\/gijon\/?$/.test(location.pathname)) return "gijon";
  return "valparaiso";
}

function safeDimensions(dimensions = {}) {
  const result = {};
  for (const [key, limit] of Object.entries(LIMITS)) {
    const value = clean(dimensions[key], limit);
    if (value) result[key] = value;
  }
  return result;
}

export function usagePayload(event, city = analyticsCity(), dimensions = {}) {
  if (!ALLOWED_EVENTS.has(event)) return null;
  if (city !== "valparaiso" && city !== "gijon") return null;
  const safe = safeDimensions(dimensions);
  return Object.keys(safe).length ? { event, city, dimensions: safe } : { event, city };
}

export function trackUsage(event, dimensions = {}, city = analyticsCity()) {
  const payload = usagePayload(event, city, dimensions);
  if (!payload) return false;
  try {
    fetch(ANALYTICS_ENDPOINT, {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      keepalive: true,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});
    return true;
  } catch {
    return false;
  }
}

function trackAppOpen() {
  if (document.body?.dataset?.eventPage !== undefined) return;
  const city = analyticsCity();
  if (sentAppOpens.has(city)) return;
  sentAppOpens.add(city);
  trackUsage("app_open", {}, city);
}

function eventContext(node) {
  const card = node?.closest?.("[data-event-id]");
  const eventId = clean(node?.dataset?.openEvent || card?.dataset?.eventId || document.body?.dataset?.eventId, LIMITS.eventId);
  const category = clean(card?.dataset?.category, LIMITS.category);
  return { eventId, category };
}

function classifyOutbound(node) {
  const text = String(node.textContent || "").toLocaleLowerCase("es");
  const classes = String(node.className || "").toLocaleLowerCase("es");
  if (/entrada|ticket/.test(text + classes)) return "tickets";
  if (/inscri|reserv/.test(text + classes)) return "registration";
  if (/open data/.test(text)) return "open_data";
  if (/fuente oficial/.test(text)) return "official";
  if (/fuente|referencia/.test(text + classes)) return "source";
  return "external";
}

function inferFilter(node) {
  if (node.matches?.("[data-section-filter]")) return ["section", node.dataset.sectionFilter];
  if (node.matches?.("[data-category-filter]")) return ["category", node.dataset.categoryFilter || "all"];
  if (node.matches?.("[data-filter-value]")) {
    const owner = node.closest("[data-combined-when],[data-combined-area],[data-combined-category-filters]");
    const filter = owner?.hasAttribute("data-combined-when") ? "when"
      : owner?.hasAttribute("data-combined-area") ? "area"
        : owner?.hasAttribute("data-combined-category-filters") ? "category" : "filter";
    return [filter, node.dataset.filterValue || "all"];
  }
  return null;
}

function onClick(event) {
  const node = event.target.closest?.("button,a");
  if (!node) return;

  const filter = inferFilter(node);
  if (filter) trackUsage("filter_apply", { filter: filter[0], value: filter[1] });

  if (node.matches("[data-open-event]")) trackUsage("event_open", eventContext(node));

  if (node.matches("[data-native-share],[data-copy-link]") || /^compartir$/i.test(String(node.textContent || "").trim())) {
    trackUsage("share", eventContext(node));
  }

  if (node.tagName === "A") {
    let url = null;
    try { url = new URL(node.href, location.href); } catch {}
    if (url?.pathname.endsWith("/evento.ics") || url?.pathname.endsWith("evento.ics")) {
      trackUsage("calendar_download", eventContext(node));
    } else if (url && url.origin !== location.origin) {
      trackUsage("outbound_open", { ...eventContext(node), target: classifyOutbound(node) });
    }
  }
}

function onChange(event) {
  const node = event.target;
  const mappings = [
    ["[data-filter-city]", "city"], ["[data-top-city]", "city"],
    ["[data-filter-category]", "category"], ["[data-top-category]", "category"],
    ["[data-filter-period]", "when"], ["[data-filter-free]", "free"],
    ["[data-filter-workshops]", "workshops"],
  ];
  for (const [selector, filter] of mappings) {
    if (!node.matches?.(selector)) continue;
    const value = node.type === "checkbox" ? (node.checked ? "on" : "off") : (node.value || "all");
    trackUsage("filter_apply", { filter, value });
    return;
  }
}

function onSearchInput(event) {
  const input = event.target;
  if (!input.matches?.('input[type="search"], [data-smart-search], [data-filter-query], [data-header-query], [data-mobile-query]')) return;
  clearTimeout(searchTimers.get(input));
  if (!String(input.value || "").trim()) return;
  searchTimers.set(input, setTimeout(() => trackUsage("search"), 800));
}

function trackPermanentEventPage() {
  if (document.body?.dataset?.eventPage === undefined) return;
  trackUsage("event_open", { eventId: document.body.dataset.eventId });
}

document.addEventListener("click", onClick, true);
document.addEventListener("change", onChange, true);
document.addEventListener("input", onSearchInput, true);
window.addEventListener("appinstalled", () => trackUsage("install"), { once: true });

new MutationObserver(trackAppOpen).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });
trackAppOpen();
trackPermanentEventPage();

export const ANALYTICS_PRIVACY = Object.freeze({
  cookies: false,
  identifiers: false,
  rawSearchQueries: false,
  coordinates: false,
  rawUrls: false,
  thirdPartyAnalytics: false,
});
