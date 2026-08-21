import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";

const grid = document.querySelector("[data-dated-grid]");
let queued = false;
let applying = false;

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/\s+/g, " ")
    .trim();
}

function directCards() {
  return [...(grid?.children || [])].filter((node) =>
    node instanceof HTMLElement && node.classList.contains("event-card"),
  );
}

function directUnifiedCards() {
  return directCards().filter((node) =>
    node.dataset.unifiedExhibitionGroup === "true" && node.dataset.eventGroup,
  );
}

function venueKey(card) {
  const venue = fold(card.querySelector("h4")?.textContent);
  const city = fold(card.querySelector(".exhibition-venue-city")?.textContent);
  return venue ? `${venue}|${city}` : null;
}

function groupedRows(card) {
  return [...card.querySelectorAll("[data-grouped-event-id]")];
}

function refreshCount(card) {
  const rows = groupedRows(card);
  const visible = rows.filter((row) => !row.hidden).length;
  const count = card.querySelector("[data-exhibition-visible-count]");
  if (count) count.textContent = `${visible} ${visible === 1 ? "exposición disponible" : "exposiciones disponibles"}`;
  const summary = card.querySelector("[data-exhibition-summary]");
  if (summary) summary.textContent = `Ver ${visible} ${visible === 1 ? "exposición" : "exposiciones"}`;
  card.hidden = visible === 0;
}

function consolidateVenueCards(cards) {
  if (cards.length < 2) {
    if (cards[0]) refreshCount(cards[0]);
    return;
  }

  const canonical = cards.reduce((best, card) => {
    if (!best) return card;
    return groupedRows(card).length > groupedRows(best).length ? card : best;
  }, null);
  if (!canonical) return;

  const list = canonical.querySelector(".exhibition-group-list");
  if (!list) return;

  const rowById = new Map();
  const visibleById = new Map();
  for (const card of cards) {
    for (const row of groupedRows(card)) {
      const id = String(row.dataset.groupedEventId || "").trim();
      if (!id) continue;
      if (!rowById.has(id)) rowById.set(id, row);
      visibleById.set(id, visibleById.get(id) === true || !row.hidden);
    }
  }

  const orderedRows = [];
  for (const [id, row] of rowById) {
    row.hidden = visibleById.get(id) !== true;
    orderedRows.push(row);
  }
  list.replaceChildren(...orderedRows);
  canonical.dataset.eventGroup = [...rowById.keys()].join(",");
  for (const card of cards) {
    if (card !== canonical) card.remove();
  }
  refreshCount(canonical);
}

function cardEventIds(card) {
  if (card.dataset.eventGroup) {
    return String(card.dataset.eventGroup).split(",").map((id) => id.trim()).filter(Boolean);
  }
  const id = String(card.dataset.eventId || "").trim();
  return id ? [id] : [];
}

function cityRank(cityName) {
  const city = fold(cityName);
  if (city.includes("vina del mar")) return 0;
  if (city.includes("valparaiso")) return 1;
  return 0;
}

function applyPresentationOrder() {
  const snapshot = getAgendaRuntimeSnapshot();
  const eventsById = new Map((snapshot?.events || [])
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));

  for (const card of directCards()) {
    const ids = cardEventIds(card);
    const event = ids.map((id) => eventsById.get(id)).find(Boolean);
    const category = String(card.dataset.category || event?.primary_category?.id || "").trim();
    const exhibitionRank = category === "exposiciones" || category === "museos" ? 100 : 0;
    const areaRank = cityRank(event?.location?.city || event?.location?.commune || "");
    card.style.order = String(exhibitionRank + areaRank);
  }
}

function applyGuard() {
  queued = false;
  if (!grid || applying) return;
  applying = true;
  try {
    const byVenue = new Map();
    for (const card of directUnifiedCards()) {
      const key = venueKey(card);
      if (!key) continue;
      const bucket = byVenue.get(key) || [];
      bucket.push(card);
      byVenue.set(key, bucket);
    }
    for (const cards of byVenue.values()) consolidateVenueCards(cards);
    applyPresentationOrder();
  } finally {
    applying = false;
  }
}

function scheduleGuard() {
  if (queued || applying) return;
  queued = true;
  queueMicrotask(applyGuard);
}

for (const eventName of [
  "vivamos:agenda-data-ready",
  "vivamos:agenda-rendered",
  "vivamos:exhibition-groups-rendered",
]) {
  window.addEventListener(eventName, scheduleGuard);
}
if (grid) new MutationObserver(scheduleGuard).observe(grid, { childList: true });
document.addEventListener("input", (event) => {
  if (event.target.matches("[data-smart-search], [data-date-from], [data-date-to]")) setTimeout(scheduleGuard, 0);
});
document.addEventListener("click", (event) => {
  if (event.target.closest("[data-filter-value], [data-combined-category], [data-filter-clear]")) setTimeout(scheduleGuard, 0);
});
scheduleGuard();
