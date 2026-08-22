import { getAgendaRuntimeSnapshot } from "./agenda-runtime-state.mjs?v=20260819-runtime1";
import { canonicalVenueKeyForEvents } from "./venue-identity.mjs?v=20260821-venueidentity1";

const grid = document.querySelector("[data-dated-grid]");
let queued = false;
let applying = false;

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

function cardEventIds(card) {
  if (card.dataset.eventGroup) {
    return String(card.dataset.eventGroup).split(",").map((id) => id.trim()).filter(Boolean);
  }
  const id = String(card.dataset.eventId || "").trim();
  return id ? [id] : [];
}

function runtimeEventsById() {
  const snapshot = getAgendaRuntimeSnapshot();
  return new Map((snapshot?.events || [])
    .map((event) => [String(event?.id || "").trim(), event])
    .filter(([id]) => id));
}

function venueKey(card, eventsById) {
  const structural = String(card.dataset.venueKey || "").trim();
  if (structural) return structural;

  const events = cardEventIds(card).map((id) => eventsById.get(id)).filter(Boolean);
  const venue = String(card.querySelector("h4")?.textContent || "").trim();
  const city = String(card.querySelector(".exhibition-venue-city")?.textContent || "").trim();
  return canonicalVenueKeyForEvents(events, { venue, city }) || null;
}

function groupedRows(card) {
  return [...card.querySelectorAll("[data-grouped-event-id]")];
}

function refreshCount(card) {
  const rows = groupedRows(card);
  const visible = rows.filter((row) => !row.hidden).length;
  const count = card.querySelector("[data-exhibition-visible-count]");
  const countText = `${visible} ${visible === 1 ? "exposición disponible" : "exposiciones disponibles"}`;
  if (count && count.textContent !== countText) count.textContent = countText;
  const summary = card.querySelector("[data-exhibition-summary]");
  const summaryText = `Ver ${visible} ${visible === 1 ? "exposición" : "exposiciones"}`;
  if (summary && summary.textContent !== summaryText) summary.textContent = summaryText;
  const shouldHide = visible === 0;
  if (card.hidden !== shouldHide) card.hidden = shouldHide;
}

function consolidateVenueCards(cards, key) {
  if (cards.length < 2) {
    if (cards[0]) {
      cards[0].dataset.venueKey = key;
      refreshCount(cards[0]);
    }
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
  canonical.dataset.venueKey = key;
  for (const card of cards) {
    if (card !== canonical) card.remove();
  }
  refreshCount(canonical);
}

function applyGuard() {
  queued = false;
  if (!grid || applying) return;
  applying = true;
  try {
    const eventsById = runtimeEventsById();
    const byVenue = new Map();
    for (const card of directUnifiedCards()) {
      const key = venueKey(card, eventsById);
      if (!key) continue;
      const bucket = byVenue.get(key) || [];
      bucket.push(card);
      byVenue.set(key, bucket);
    }
    for (const [key, cards] of byVenue) consolidateVenueCards(cards, key);
  } finally {
    applying = false;
  }
}

function scheduleGuard() {
  if (queued || applying) return;
  queued = true;
  // Consolidation is presentation work. Agenda ordering has a single owner in
  // agenda-order-core/app.js and is intentionally not rewritten here.
  if (typeof window.requestAnimationFrame === "function") {
    window.requestAnimationFrame(applyGuard);
  } else {
    window.setTimeout(applyGuard, 0);
  }
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
