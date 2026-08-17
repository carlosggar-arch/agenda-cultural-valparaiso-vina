const STYLE_ID = "combined-filters-runtime-polish";
const REJECTED_EVENT_IDS = new Set([
  "agenda_968c623b60b70d2976410175",
]);

const EDITORIAL_SOCIAL_CUES = [
  /\bsabias que\b/,
  /\bte contamos\b/,
  /\bcuriosidades?\b/,
  /\bdatos (?:de|sobre)\b/,
  /\bdetras de (?:camara|camaras|escena|escenas)\b/,
  /\bmaking of\b/,
  /\btrivia\b/,
  /\bcine dentro del cine\b/,
  /\bdesliza\b/,
  /\bconoce (?:mas|la historia|los detalles|detalles)\b/,
  /\bdescubre (?:mas|la historia|los detalles|detalles)\b/,
];

if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .legacy-filter-hooks { display: none !important; }
    .hero .smart-search input { padding-left: 2.75rem !important; }
    .filter-workbench { margin-top: 0 !important; }
    .event-card[hidden] { display: none !important; }
    .event-card[data-event-id="agenda_968c623b60b70d2976410175"] { display: none !important; }
  `;
  document.head.append(style);
}

function fold(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/\s+/g, " ")
    .trim();
}

function sourceUrl(event) {
  return String(event?.source_url || event?.links?.source || event?.links?.official || "");
}

function hasConcreteEventEvidence(event) {
  return Boolean(
    String(event?.location?.venue || "").trim()
    || String(event?.location?.address || "").trim()
    || String(event?.organizer || "").trim()
    || String(event?.links?.tickets || "").trim()
    || String(event?.links?.registration || "").trim()
    || String(event?.registration_requirements || "").trim()
  );
}

function hasEditorialSocialLanguage(event) {
  const text = fold(`${event?.title || ""} ${event?.description || ""}`);
  return EDITORIAL_SOCIAL_CUES.some((pattern) => pattern.test(text));
}

function isEditorialSocialFalsePositive(event) {
  if (!String(sourceUrl(event)).includes("instagram.com")) return false;
  if (event?.event_type && event.event_type !== "event") return false;
  if (event?.public_status?.information_completeness === "complete") return false;
  if (hasConcreteEventEvidence(event)) return false;
  return hasEditorialSocialLanguage(event);
}

function currentDatasetUrl() {
  return document.documentElement.dataset.city === "gijon"
    ? "./data/gijon/agenda_web.json"
    : "../agenda_web.json";
}

async function refreshEditorialRejections() {
  try {
    const response = await fetch(currentDatasetUrl(), { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    for (const event of payload?.events || []) {
      if (isEditorialSocialFalsePositive(event)) REJECTED_EVENT_IDS.add(String(event.id || ""));
    }
    removeRejectedEditorialCards();
  } catch {
    // La protección por IDs conocidos sigue activa aunque el diagnóstico adicional no pueda cargarse.
  }
}

function removeNonActionableFilterCopy() {
  for (const selector of [
    ".discovery-heading",
    ".filter-workbench-heading",
    ".category-explorer-heading",
    ".filter-help",
  ]) {
    document.querySelector(selector)?.remove();
  }
}

function removePriceFilter() {
  document.querySelector("[data-combined-price]")?.closest(".filter-group")?.remove();
}

function clearRemovedFilterState() {
  const url = new URL(window.location.href);
  let changed = false;
  for (const key of ["price", "access", "format", "aud"]) {
    if (!url.searchParams.has(key)) continue;
    url.searchParams.delete(key);
    changed = true;
  }
  if (!changed) return;
  const next = `${url.pathname}${url.search}${url.hash}`;
  history.replaceState(null, "", next);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function preserveScrollDuringLegacyClick(container) {
  container?.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const top = window.scrollY;
    requestAnimationFrame(() => window.scrollTo({ top, left: 0, behavior: "auto" }));
  }, true);
}

function refreshVisibleTotals() {
  let total = 0;
  for (const [sectionSelector, totalSelector, gridSelector] of [
    ["[data-dated-section]", "[data-dated-total]", "[data-dated-grid]"],
    ["[data-program-section]", "[data-program-total]", "[data-program-grid]"],
    ["[data-flexible-section]", "[data-flexible-total]", "[data-flexible-grid]"],
  ]) {
    const section = document.querySelector(sectionSelector);
    const counter = document.querySelector(totalSelector);
    const grid = document.querySelector(gridSelector);
    const count = grid?.querySelectorAll(".event-card[data-event-id]").length || 0;
    if (counter) counter.textContent = String(count);
    if (section) section.hidden = count === 0;
    total += count;
  }
  const overall = document.querySelector("[data-total]");
  if (overall) overall.textContent = String(total);
}

function shouldRejectEditorialCard(card) {
  const id = card.dataset.eventId || "";
  if (REJECTED_EVENT_IDS.has(id)) return true;
  const text = fold(card.textContent || "");
  return text.includes("instagram.com")
    && text.includes("sabias que")
    && text.includes("campamento")
    && text.includes("cine dentro del cine");
}

function removeRejectedEditorialCards() {
  let removed = false;
  for (const card of document.querySelectorAll(".event-card[data-event-id]")) {
    if (!shouldRejectEditorialCard(card)) continue;
    card.remove();
    removed = true;
  }
  if (removed) refreshVisibleTotals();
}

function hasCombinedFilterState() {
  const params = new URLSearchParams(window.location.search);
  return ["when", "area", "cat", "q", "from", "to"].some((key) => params.has(key));
}

let resyncQueued = false;
function queueFilterResync() {
  removeRejectedEditorialCards();
  if (!hasCombinedFilterState() || resyncQueued) return;
  resyncQueued = true;
  requestAnimationFrame(() => {
    resyncQueued = false;
    window.dispatchEvent(new PopStateEvent("popstate"));
    requestAnimationFrame(removeRejectedEditorialCards);
  });
}

for (const grid of document.querySelectorAll("[data-dated-grid], [data-program-grid], [data-flexible-grid]")) {
  new MutationObserver(queueFilterResync).observe(grid, { childList: true });
}

new MutationObserver(() => {
  REJECTED_EVENT_IDS.clear();
  REJECTED_EVENT_IDS.add("agenda_968c623b60b70d2976410175");
  refreshEditorialRejections();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

removeNonActionableFilterCopy();
removePriceFilter();
clearRemovedFilterState();
removeRejectedEditorialCards();
refreshEditorialRejections();
preserveScrollDuringLegacyClick(document.querySelector("[data-section-filters]"));
preserveScrollDuringLegacyClick(document.querySelector("[data-category-filters]"));

requestAnimationFrame(() => window.scrollTo({ top: 0, left: 0, behavior: "auto" }));