import { loadCityRegistry } from "../assets/city-registry.mjs?v=20260817-city-registry";
import {
  organizeTemporalPriority,
  temporalBadge,
  shouldSuppressForTemporalFilter,
} from "./temporal-priority-core.mjs?v=20260819-temporal1";

const CITY_REGISTRY = await loadCityRegistry();
const CITY_CONFIG = CITY_REGISTRY.byId;
const DEFAULT_CITY_ID = CITY_REGISTRY.defaultCityId;
const PRIORITY_BLOCKS = [
  { key: "today", title: "Hoy / No te lo pierdas", limit: 8 },
  { key: "endingSoon", title: "Terminan pronto", limit: 8 },
  { key: "upcoming", title: "Próximos eventos puntuales", limit: 8 },
  { key: "exhibitions", title: "Exposiciones y muestras vigentes", limit: 12, groupExhibitions: true },
];

let dataset = null;
let city = null;
let loadingToken = 0;
let applyingGuard = false;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function currentCity() {
  const id = document.documentElement.dataset.city;
  return CITY_CONFIG[id] || CITY_CONFIG[DEFAULT_CITY_ID] || null;
}

function safeUrl(value) {
  try {
    const url = new URL(value, window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function eventLink(event) {
  return safeUrl(event?.links?.official || event?.links?.source || event?.source_url);
}

function eventCategory(event) {
  const category = event?.primary_category || event?.categories?.[0];
  const label = String(category?.label || "Actividad cultural").trim();
  return /museo/i.test(label) ? "Exposiciones" : label;
}

function scheduleText(event) {
  return String(event?.schedule?.display_text || "Horario por confirmar").trim();
}

function locationText(event) {
  return [event?.location?.venue, event?.location?.city].filter(Boolean).join(" · ") || "Lugar por confirmar";
}

function simpleCard(event) {
  const badge = temporalBadge(event, city, new Date());
  const link = eventLink(event);
  const article = document.createElement("article");
  article.className = "event-card temporal-priority-card";
  article.dataset.temporalEventId = event?.id || "";
  article.innerHTML = `
    <div class="card-meta-row">
      <span class="meta">${escapeHtml(eventCategory(event))}</span>
      ${badge ? `<span class="temporal-urgency-badge">${escapeHtml(badge)}</span>` : ""}
    </div>
    <h4>${escapeHtml(event?.title || "Actividad sin título")}</h4>
    <p>${escapeHtml(scheduleText(event))}</p>
    <p>${escapeHtml(locationText(event))}</p>
    <div class="event-bottom">
      <span>${event?.price?.is_free === true ? "Gratis" : escapeHtml(event?.price?.display_text || "Precio por confirmar")}</span>
      ${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}
    </div>`;
  return article;
}

function exhibitionVenueKey(event) {
  return [event?.location?.venue, event?.location?.city].filter(Boolean).join("||| ").toLocaleLowerCase(city?.locale || "es");
}

function exhibitionGroupCard(events) {
  if (events.length < 3) return events.map(simpleCard);
  const first = events[0];
  const article = document.createElement("article");
  article.className = "event-card temporal-priority-card temporal-exhibition-group";
  const venue = first?.location?.venue || "Espacio cultural";
  const place = first?.location?.city || "";
  const items = events.map((event) => {
    const link = eventLink(event);
    return `<li><strong>${escapeHtml(event?.title || "Exposición")}</strong><small>${escapeHtml(scheduleText(event))}</small>${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}</li>`;
  }).join("");
  article.innerHTML = `
    <div class="card-meta-row"><span class="meta">Exposiciones</span></div>
    <h4>${escapeHtml(venue)}</h4>
    <p><strong>${events.length} exposiciones vigentes</strong>${place ? ` · ${escapeHtml(place)}` : ""}</p>
    <details><summary>Ver exposiciones</summary><ul>${items}</ul></details>`;
  return [article];
}

function cardsForBlock(events, block) {
  const limited = events.slice(0, block.limit);
  if (!block.groupExhibitions) return limited.map(simpleCard);
  const buckets = new Map();
  for (const event of limited) {
    const key = exhibitionVenueKey(event);
    const items = buckets.get(key) || [];
    items.push(event);
    buckets.set(key, items);
  }
  return [...buckets.values()].flatMap(exhibitionGroupCard);
}

function ensureStyles() {
  if (document.querySelector("style[data-temporal-priority-styles]")) return;
  const style = document.createElement("style");
  style.dataset.temporalPriorityStyles = "";
  style.textContent = `
    .temporal-priority{width:min(1120px,calc(100% - 2rem));margin:0 auto 1.2rem;padding:.4rem 0 1.5rem}
    .temporal-priority[hidden]{display:none}
    .temporal-priority-heading{display:flex;align-items:end;justify-content:space-between;gap:1rem;margin-bottom:1rem}
    .temporal-priority-heading h2{font-family:Georgia,serif;font-size:clamp(1.8rem,4vw,2.45rem);margin:0;color:var(--brand,#174f46)}
    .temporal-priority-heading p{margin:.35rem 0 0;color:var(--muted,#62756f);max-width:700px;line-height:1.5}
    .temporal-priority-block{padding:1.15rem 0 1.35rem;border-top:1px solid var(--line,rgba(23,79,70,.14))}
    .temporal-priority-block:first-child{border-top:0}
    .temporal-priority-block-heading{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin-bottom:.9rem}
    .temporal-priority-block-heading h3{font-family:Georgia,serif;font-size:1.45rem;margin:0;color:var(--brand,#174f46)}
    .temporal-priority-count{font-size:.82rem;color:var(--muted,#62756f);white-space:nowrap}
    .temporal-priority-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}
    .temporal-priority-card{min-height:0}
    .temporal-urgency-badge{font-size:.72rem;font-weight:850;color:#8a3d00;background:#fff0df;border:1px solid #ecc28c;border-radius:999px;padding:.28rem .52rem;white-space:nowrap}
    .temporal-exhibition-group details{margin-top:.2rem}.temporal-exhibition-group summary{cursor:pointer;font-weight:800;color:var(--brand,#174f46)}
    .temporal-exhibition-group ul{list-style:none;padding:0;margin:.75rem 0 0;display:grid;gap:.7rem}
    .temporal-exhibition-group li{display:grid;gap:.18rem;padding-top:.65rem;border-top:1px solid var(--line,rgba(23,79,70,.14))}
    .temporal-exhibition-group small{color:var(--muted,#62756f)}
    .temporal-exhibition-group a{width:max-content;max-width:100%}
    .event-card[data-temporal-suppressed="true"]{display:none!important}
    @media(max-width:800px){.temporal-priority-grid{grid-template-columns:1fr 1fr}}
    @media(max-width:560px){.temporal-priority-grid{grid-template-columns:1fr}.temporal-priority-heading,.temporal-priority-block-heading{align-items:flex-start;flex-direction:column;gap:.35rem}.temporal-priority-count{white-space:normal}}
  `;
  document.head.append(style);
}

function ensureContainer() {
  let section = document.querySelector("[data-temporal-priority]");
  if (section) return section;
  const agenda = document.querySelector("[data-agenda]");
  if (!agenda?.parentNode) return null;
  section = document.createElement("section");
  section.className = "temporal-priority";
  section.dataset.temporalPriority = "";
  section.hidden = true;
  section.setAttribute("aria-labelledby", "temporal-priority-title");
  section.innerHTML = `
    <div class="temporal-priority-heading">
      <div><p class="eyebrow">Prioridad temporal</p><h2 id="temporal-priority-title">Lo más relevante ahora</h2><p>Primero las citas que requieren atención; después, las exposiciones que siguen vigentes.</p></div>
    </div>
    <div data-temporal-priority-blocks></div>`;
  agenda.parentNode.insertBefore(section, agenda);
  return section;
}

function filtersAreNeutral() {
  const when = activeWhenFilter();
  const area = document.querySelector('[data-combined-area] [data-filter-value].active')?.dataset?.filterValue || "todos";
  const query = String(document.querySelector("[data-smart-search]")?.value || document.querySelector("[data-search]")?.value || "").trim();
  const categories = [...document.querySelectorAll("[data-combined-category-filters] [data-filter-value].active")].filter((button) => button.dataset.filterValue && button.dataset.filterValue !== "todos");
  return when === "todos" && area === "todos" && !query && categories.length === 0;
}

function renderPriority() {
  const section = ensureContainer();
  const target = section?.querySelector("[data-temporal-priority-blocks]");
  if (!section || !target || !city || !Array.isArray(dataset?.events)) return;
  if (!filtersAreNeutral()) { section.hidden = true; return; }
  const blocks = organizeTemporalPriority(dataset.events, city, new Date());
  target.replaceChildren();
  let visibleBlocks = 0;
  for (const block of PRIORITY_BLOCKS) {
    const events = blocks[block.key] || [];
    if (!events.length) continue;
    visibleBlocks += 1;
    const node = document.createElement("section");
    node.className = "temporal-priority-block";
    const heading = document.createElement("div");
    heading.className = "temporal-priority-block-heading";
    heading.innerHTML = `<h3>${escapeHtml(block.title)}</h3><span class="temporal-priority-count">${events.length} ${events.length === 1 ? "actividad" : "actividades"}</span>`;
    const grid = document.createElement("div");
    grid.className = "temporal-priority-grid";
    grid.append(...cardsForBlock(events, block));
    node.append(heading, grid);
    target.append(node);
  }
  section.hidden = visibleBlocks === 0;
}

function activeWhenFilter() {
  const visible = document.querySelector('[data-combined-when] [data-filter-value].active');
  if (visible?.dataset?.filterValue) return visible.dataset.filterValue;
  const legacy = document.querySelector('[data-section-filters] [data-section-filter].active');
  return legacy?.dataset?.sectionFilter || "todos";
}

function eventMap() {
  return new Map((dataset?.events || []).map((event) => [String(event?.id || ""), event]));
}

function applyTemporalFilterGuard() {
  if (applyingGuard || !dataset || !city) return;
  applyingGuard = true;
  try {
    const when = activeWhenFilter();
    const byId = eventMap();
    for (const card of document.querySelectorAll('[data-agenda] .event-card[data-event-id]')) {
      const item = byId.get(String(card.dataset.eventId || ""));
      const suppress = item ? shouldSuppressForTemporalFilter(item, when) : false;
      if (suppress) card.dataset.temporalSuppressed = "true";
      else delete card.dataset.temporalSuppressed;

      const row = card.querySelector(".card-meta-row");
      if (item && row && !row.querySelector(".temporal-urgency-badge")) {
        const badge = temporalBadge(item, city, new Date());
        if (badge) {
          const span = document.createElement("span");
          span.className = "temporal-urgency-badge";
          span.textContent = badge;
          row.append(span);
        }
      }
    }

    if (when !== "todos") {
      const visibleDated = document.querySelectorAll('[data-dated-grid] .event-card:not([data-temporal-suppressed="true"])').length;
      const datedTotal = document.querySelector("[data-dated-total]");
      if (datedTotal && datedTotal.textContent !== String(visibleDated)) datedTotal.textContent = String(visibleDated);
      const total = document.querySelector("[data-total]");
      const visiblePrograms = document.querySelectorAll('[data-program-grid] .event-card:not([data-temporal-suppressed="true"])').length;
      const visibleFlexible = document.querySelectorAll('[data-flexible-grid] .event-card:not([data-temporal-suppressed="true"])').length;
      const visibleTotal = String(visibleDated + visiblePrograms + visibleFlexible);
      if (total && total.textContent !== visibleTotal) total.textContent = visibleTotal;
    }
  } finally {
    applyingGuard = false;
  }
}

function scheduleGuard() {
  queueMicrotask(() => {
    renderPriority();
    applyTemporalFilterGuard();
  });
}

async function loadDatasetForCity(nextCity) {
  const token = ++loadingToken;
  city = nextCity;
  dataset = null;
  const section = ensureContainer();
  if (section) section.hidden = true;
  try {
    const response = await fetch(nextCity.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (token !== loadingToken) return;
    if (!Array.isArray(payload?.events)) throw new Error("Dataset inválido");
    dataset = payload;
    scheduleGuard();
  } catch {
    if (token !== loadingToken) return;
    dataset = null;
  }
}

function refreshCity() {
  const next = currentCity();
  if (!next || next.id === city?.id) return;
  loadDatasetForCity(next);
}

ensureStyles();
ensureContainer();
refreshCity();

new MutationObserver(() => scheduleGuard()).observe(document.querySelector("[data-agenda]") || document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["class", "data-event-id"],
});
new MutationObserver(refreshCity).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});
document.addEventListener("click", (event) => {
  if (event.target.closest("[data-filter-value], [data-section-filter], [data-category-filter]")) scheduleGuard();
}, true);
document.addEventListener("input", (event) => {
  if (event.target.matches("[data-smart-search], [data-search], [data-date-from], [data-date-to]")) scheduleGuard();
}, true);
