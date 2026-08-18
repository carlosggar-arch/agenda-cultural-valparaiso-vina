import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";

const CITY_REGISTRY = await loadCityRegistry();
const CITIES = CITY_REGISTRY.byId;
const EXHIBITION_ID = "exposiciones";
const MAX_COLLAGE_IMAGES = 5;
const grid = document.querySelector("[data-dated-grid]");

let eventsById = new Map();
let loadedCity = null;
let loadToken = 0;
let syncQueued = false;

function installStylesheet() {
  if (document.querySelector("link[data-exhibition-gallery-styles]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = new URL("./exhibition-gallery.css?v=20260818-gallery2", import.meta.url).href;
  link.dataset.exhibitionGalleryStyles = "";
  document.head.append(link);
}

function currentCityId() {
  const id = String(document.documentElement.dataset.city || "").trim();
  return CITIES[id] ? id : null;
}

function currentCity() {
  return CITIES[currentCityId()] || null;
}

function dateKey(value, city) {
  if (!value) return null;
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: city.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function formatDate(value, city, includeWeekday = false) {
  const key = dateKey(value, city);
  if (!key) return String(value || "");
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12));
  return new Intl.DateTimeFormat(city.locale || "es", {
    timeZone: "UTC",
    weekday: includeWeekday ? "short" : undefined,
    day: "numeric",
    month: "short",
    year: year !== new Date().getFullYear() ? "numeric" : undefined,
  }).format(date);
}

function formatTime(value, city) {
  if (!value || /^\d{4}-\d{2}-\d{2}$/.test(String(value))) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(city.locale || "es", {
    timeZone: city.timezone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function scheduleLabel(event) {
  const city = currentCity();
  if (!city) return event?.schedule?.display_text || "Horario por confirmar";
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  const end = event?.schedule?.end;
  if (!start) return event?.schedule?.display_text || "Horario por confirmar";

  const startKey = dateKey(start, city);
  const endKey = dateKey(end, city);
  const today = dateKey(new Date(), city);
  if (startKey && endKey && startKey !== endKey) {
    if (startKey <= today && endKey >= today) return `En exhibición hasta el ${formatDate(end, city)}`;
    return `${formatDate(start, city)} – ${formatDate(end, city)}`;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(String(start))) return formatDate(start, city, true);
  const time = formatTime(start, city);
  return `${formatDate(start, city, true)}${time ? `, ${time}` : ""}`;
}

function openingTime(event) {
  const city = currentCity();
  if (!city) return null;
  const enriched = event?.editorial?.venue_hours_enriched === true
    || event?.editorial?.visit_hours_enriched === true;
  if (!enriched) return null;
  const start = event?.schedule?.start || event?.schedule?.occurrences?.[0]?.start;
  return formatTime(start, city);
}

function eventImage(event) {
  const url = String(event?.image?.url || "").trim();
  if (!url) return null;
  return {
    url,
    alt: String(event?.image?.alt || event?.title || "Exposición").trim() || "Exposición",
  };
}

function eventLink(event) {
  const candidate = event?.links?.official || event?.links?.source;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function priceLabel(event) {
  if (event?.price?.is_free === true) return "Gratis";
  return String(event?.price?.display_text || "").trim();
}

function proxyRoot() {
  let root = document.querySelector("[data-exhibition-filter-proxies]");
  if (root) return root;
  root = document.createElement("div");
  root.dataset.exhibitionFilterProxies = "";
  root.setAttribute("aria-hidden", "true");
  root.className = "exhibition-filter-proxies";
  document.body.append(root);
  new MutationObserver(queueSync).observe(root, {
    attributes: true,
    attributeFilter: ["hidden"],
    subtree: true,
    childList: true,
  });
  return root;
}

function ensureProxy(id) {
  const root = proxyRoot();
  let proxy = root.querySelector(`[data-exhibition-proxy-id="${CSS.escape(id)}"]`);
  if (proxy) return proxy;
  proxy = document.createElement("span");
  proxy.className = "event-card exhibition-filter-proxy";
  proxy.dataset.eventId = id;
  proxy.dataset.exhibitionProxyId = id;
  proxy.setAttribute("aria-hidden", "true");
  root.append(proxy);
  return proxy;
}

function groupIds(card) {
  return String(card.dataset.eventGroup || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
}

function sortedEvents(ids) {
  return ids
    .map((id) => eventsById.get(id))
    .filter(Boolean)
    .sort((a, b) => {
      const aStart = String(a?.schedule?.start || a?.schedule?.occurrences?.[0]?.start || "9999");
      const bStart = String(b?.schedule?.start || b?.schedule?.occurrences?.[0]?.start || "9999");
      return aStart.localeCompare(bStart) || String(a?.title || "").localeCompare(String(b?.title || ""), "es");
    });
}

function uniqueImages(events) {
  const images = [];
  const seen = new Set();
  for (const event of events) {
    const image = eventImage(event);
    if (!image || seen.has(image.url)) continue;
    seen.add(image.url);
    images.push(image);
    if (images.length >= MAX_COLLAGE_IMAGES) break;
  }
  return images;
}

function buildCollage(card, events) {
  const collage = card.querySelector("[data-exhibition-collage]");
  if (!collage) return;
  const images = uniqueImages(events);
  const signature = images.map((image) => image.url).join("|");
  if (collage.dataset.signature === signature) return;
  collage.dataset.signature = signature;
  collage.replaceChildren();
  collage.dataset.count = String(images.length);

  if (!images.length) {
    const placeholder = document.createElement("div");
    placeholder.className = "exhibition-collage-placeholder";
    placeholder.innerHTML = "<span aria-hidden=\"true\">▧</span><strong>Exposiciones</strong>";
    collage.append(placeholder);
    return;
  }

  for (const image of images) {
    const tile = document.createElement("div");
    tile.className = "exhibition-collage-tile";
    const img = document.createElement("img");
    img.src = image.url;
    img.alt = image.alt;
    img.loading = "lazy";
    img.decoding = "async";
    img.addEventListener("error", () => tile.classList.add("image-error"), { once: true });
    tile.append(img);
    collage.append(tile);
  }
}

function buildRow(event) {
  const row = document.createElement("article");
  row.className = "grouped-exhibition-item";
  row.dataset.groupedEventId = String(event?.id || "");

  const media = document.createElement("div");
  media.className = "grouped-exhibition-media";
  const image = eventImage(event);
  if (image) {
    const img = document.createElement("img");
    img.src = image.url;
    img.alt = image.alt;
    img.loading = "lazy";
    img.decoding = "async";
    img.addEventListener("error", () => media.classList.add("image-error"), { once: true });
    media.append(img);
  } else {
    media.classList.add("image-error");
  }

  const copy = document.createElement("div");
  copy.className = "grouped-exhibition-copy";
  const title = document.createElement("strong");
  title.textContent = event?.title || "Exposición sin título";
  const schedule = document.createElement("small");
  schedule.textContent = scheduleLabel(event);
  copy.append(title, schedule);

  const price = priceLabel(event);
  if (price) {
    const priceNode = document.createElement("span");
    priceNode.className = "grouped-exhibition-price";
    priceNode.textContent = price;
    copy.append(priceNode);
  }

  const actions = document.createElement("div");
  actions.className = "grouped-exhibition-actions";
  const href = eventLink(event);
  if (href) {
    const link = document.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Ver fuente →";
    actions.append(link);
  }

  row.append(media, copy, actions);
  return row;
}

function venueIcon() {
  const icon = document.createElement("span");
  icon.className = "exhibition-venue-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "▧";
  return icon;
}

function enhanceGroupCard(card) {
  const ids = groupIds(card);
  if (!ids.length || !eventsById.size) return;
  const events = sortedEvents(ids);
  if (!events.length) return;
  const signature = ids.join("|");
  if (card.dataset.gallerySignature === signature) {
    ids.forEach(ensureProxy);
    return;
  }

  const first = events[0];
  const venue = String(first?.location?.venue || "Espacio cultural").trim() || "Espacio cultural";
  const city = String(first?.location?.city || "").trim();

  card.classList.add("exhibition-venue-card");
  card.dataset.gallerySignature = signature;
  card.dataset.category = EXHIBITION_ID;
  card.replaceChildren();

  const collage = document.createElement("div");
  collage.className = "exhibition-collage";
  collage.dataset.exhibitionCollage = "";

  const body = document.createElement("div");
  body.className = "exhibition-venue-body";

  const meta = document.createElement("div");
  meta.className = "exhibition-venue-meta";
  meta.textContent = "Exposiciones";

  const heading = document.createElement("div");
  heading.className = "exhibition-venue-heading";
  const icon = venueIcon();
  const headingCopy = document.createElement("div");
  const title = document.createElement("h4");
  title.textContent = venue;
  const count = document.createElement("p");
  count.className = "exhibition-venue-count";
  count.dataset.exhibitionVisibleCount = "";
  headingCopy.append(title, count);
  heading.append(icon, headingCopy);

  const facts = document.createElement("div");
  facts.className = "exhibition-venue-facts";
  if (city) {
    const cityNode = document.createElement("p");
    cityNode.className = "exhibition-venue-city";
    cityNode.innerHTML = `<span aria-hidden="true">⌖</span><span></span>`;
    cityNode.lastElementChild.textContent = city;
    facts.append(cityNode);
  }
  const hours = document.createElement("p");
  hours.className = "venue-opening-hours exhibition-venue-hours";
  hours.dataset.exhibitionOpeningHours = "";
  facts.append(hours);

  const details = document.createElement("details");
  details.className = "exhibition-group-details";
  details.open = true;
  const summary = document.createElement("summary");
  summary.dataset.exhibitionSummary = "";
  details.append(summary);
  const list = document.createElement("div");
  list.className = "exhibition-group-list";
  for (const event of events) list.append(buildRow(event));
  details.append(list);

  body.append(meta, heading, facts, details);
  card.append(collage, body);
  ids.forEach(ensureProxy);
  buildCollage(card, events);
}

function visibleGroupEvents(card) {
  const ids = groupIds(card);
  return ids
    .filter((id) => {
      const proxy = ensureProxy(id);
      return !proxy.hidden;
    })
    .map((id) => eventsById.get(id))
    .filter(Boolean);
}

function syncGroupCard(card) {
  enhanceGroupCard(card);
  if (!card.classList.contains("exhibition-venue-card")) return;
  const visibleEvents = visibleGroupEvents(card);
  const visibleIds = new Set(visibleEvents.map((event) => String(event?.id || "")));
  card.hidden = visibleEvents.length === 0;

  for (const row of card.querySelectorAll("[data-grouped-event-id]")) {
    row.hidden = !visibleIds.has(row.dataset.groupedEventId || "");
  }

  const count = card.querySelector("[data-exhibition-visible-count]");
  if (count) count.textContent = `${visibleEvents.length} ${visibleEvents.length === 1 ? "exposición disponible" : "exposiciones disponibles"}`;
  const summary = card.querySelector("[data-exhibition-summary]");
  if (summary) summary.textContent = `Ver ${visibleEvents.length} ${visibleEvents.length === 1 ? "exposición" : "exposiciones"}`;

  const hours = [...new Set(visibleEvents.map(openingTime).filter(Boolean))];
  const hoursNode = card.querySelector("[data-exhibition-opening-hours]");
  if (hoursNode) {
    hoursNode.hidden = hours.length === 0;
    if (hours.length === 1) hoursNode.innerHTML = `<span aria-hidden="true">◷</span><span>Horario de apertura del recinto: ${hours[0]}</span>`;
    else if (hours.length > 1) hoursNode.innerHTML = `<span aria-hidden="true">◷</span><span>Horarios de apertura: ${hours.join(" · ")}</span>`;
  }

  buildCollage(card, visibleEvents.length ? visibleEvents : sortedEvents(groupIds(card)));
}

function syncCounts() {
  const datedTotal = document.querySelector("[data-dated-total]");
  const programTotal = document.querySelector("[data-program-total]");
  const flexibleTotal = document.querySelector("[data-flexible-total]");
  const totalNode = document.querySelector("[data-total]");
  const summary = document.querySelector("[data-filter-summary]");

  const standaloneDated = [...(grid?.querySelectorAll(".event-card[data-event-id]") || [])]
    .filter((card) => !card.hidden).length;
  const groupedIds = new Set();
  for (const card of grid?.querySelectorAll(".exhibition-venue-card:not([hidden])") || []) {
    for (const event of visibleGroupEvents(card)) groupedIds.add(String(event?.id || ""));
  }
  const dated = standaloneDated + groupedIds.size;
  const program = [...(document.querySelectorAll("[data-program-grid] .event-card[data-event-id]"))].filter((card) => !card.hidden).length;
  const flexible = [...(document.querySelectorAll("[data-flexible-grid] .event-card[data-event-id]"))].filter((card) => !card.hidden).length;
  const total = dated + program + flexible;

  if (datedTotal) datedTotal.textContent = String(dated);
  if (programTotal) programTotal.textContent = String(program);
  if (flexibleTotal) flexibleTotal.textContent = String(flexible);
  if (totalNode) totalNode.textContent = String(total);
  if (summary?.textContent) {
    summary.textContent = summary.textContent.replace(/^\d+\s+actividades?/, `${total} ${total === 1 ? "actividad" : "actividades"}`);
  }
}

function syncAll() {
  syncQueued = false;
  if (!grid || !eventsById.size) return;
  for (const card of grid.querySelectorAll(".exhibition-group-card[data-event-group]")) syncGroupCard(card);
  syncCounts();
}

function queueSync() {
  if (syncQueued) return;
  syncQueued = true;
  requestAnimationFrame(syncAll);
}

function forceCombinedFilterRefresh() {
  const search = document.querySelector("[data-smart-search]");
  if (!search) return;
  setTimeout(() => search.dispatchEvent(new Event("input", { bubbles: true })), 0);
}

async function loadDataset() {
  const cityId = currentCityId();
  if (!cityId) return;
  if (loadedCity === cityId && eventsById.size) {
    queueSync();
    return;
  }
  const token = ++loadToken;
  loadedCity = cityId;
  eventsById = new Map();
  try {
    const response = await fetch(CITIES[cityId].dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return;
    const dataset = await response.json();
    if (token !== loadToken || !Array.isArray(dataset.events)) return;
    eventsById = new Map(dataset.events.map((event) => [String(event?.id || ""), event]).filter(([id]) => id));
    queueSync();
    forceCombinedFilterRefresh();
  } catch {
    eventsById = new Map();
  }
}

installStylesheet();
proxyRoot();

if (grid) {
  new MutationObserver(() => {
    queueSync();
    if (!eventsById.size) loadDataset();
  }).observe(grid, { childList: true, subtree: true });
}

const discovery = document.querySelector("[data-discovery]");
discovery?.addEventListener("click", () => setTimeout(queueSync, 0));
discovery?.addEventListener("input", () => setTimeout(queueSync, 0));
discovery?.addEventListener("change", () => setTimeout(queueSync, 0));

new MutationObserver(() => {
  loadedCity = null;
  eventsById = new Map();
  const root = document.querySelector("[data-exhibition-filter-proxies]");
  root?.replaceChildren();
  loadDataset();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

window.addEventListener("popstate", () => setTimeout(queueSync, 0));
loadDataset();
