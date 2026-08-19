const GIJON_ID = "gijon";
const DATASET_URL = "./data/gijon/agenda_web.json";

let eventsById = new Map();
let loading = null;
let scheduled = false;

function isGijon() {
  return String(document.documentElement.dataset.city || "") === GIJON_ID;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeLink(event) {
  const candidate = event?.links?.official || event?.links?.source;
  try {
    const url = new URL(candidate);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function category(event) {
  const source = event?.primary_category || event?.categories?.[0] || {};
  return {
    id: String(source?.id || "exposiciones").trim() || "exposiciones",
    label: String(source?.label || "Exposiciones").trim() || "Exposiciones",
  };
}

function locationLabel(event) {
  const venue = String(event?.location?.venue || "").trim();
  const city = String(event?.location?.city || "").trim();
  if (venue && city && venue.toLocaleLowerCase("es") !== city.toLocaleLowerCase("es")) return `${venue} · ${city}`;
  return venue || city || "Lugar por confirmar";
}

function priceLabel(event) {
  if (event?.price?.is_free === true) return "Gratis";
  return String(event?.price?.display_text || "Consultar condiciones").trim() || "Consultar condiciones";
}

async function ensureIndex() {
  if (eventsById.size) return true;
  if (loading) return loading;
  loading = (async () => {
    try {
      const response = await fetch(DATASET_URL, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) return false;
      const payload = await response.json();
      if (!Array.isArray(payload?.events)) return false;
      eventsById = new Map(payload.events
        .map((event) => [String(event?.id || "").trim(), event])
        .filter(([id]) => id));
      return eventsById.size > 0;
    } catch {
      return false;
    } finally {
      loading = null;
    }
  })();
  return loading;
}

function createCard(event, scheduleText = "") {
  const card = document.createElement("article");
  const cat = category(event);
  const link = safeLink(event);
  card.className = "event-card event-card--dated";
  card.dataset.eventId = String(event?.id || "");
  card.dataset.category = cat.id;
  card.innerHTML = `
    <div class="card-meta-row"><span class="meta">${escapeHtml(cat.label)}</span></div>
    <h4>${escapeHtml(event?.title || "Actividad sin título")}</h4>
    <p>${escapeHtml(scheduleText || event?.schedule?.display_text || event?.schedule?.start || "Horario por confirmar")}</p>
    <p>${escapeHtml(locationLabel(event))}</p>
    <div class="event-bottom">
      <span>${escapeHtml(priceLabel(event))}</span>
      ${link ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">Ver fuente →</a>` : ""}
    </div>`;
  return card;
}

async function expandGroups() {
  scheduled = false;
  if (!isGijon()) return;
  if (!(await ensureIndex())) return;
  const grid = document.querySelector("[data-dated-grid]");
  if (!grid) return;

  let changed = false;
  for (const group of [...grid.querySelectorAll(':scope > .exhibition-group-card[data-event-group]')]) {
    const ids = String(group.dataset.eventGroup || "").split(",").map((id) => id.trim()).filter(Boolean);
    if (!ids.length) continue;
    const rows = [...group.querySelectorAll(".grouped-exhibition-item")];
    const fragment = document.createDocumentFragment();
    let inserted = 0;
    ids.forEach((id, index) => {
      const event = eventsById.get(id);
      if (!event) return;
      const scheduleText = String(rows[index]?.querySelector("small")?.textContent || "").trim();
      fragment.append(createCard(event, scheduleText));
      inserted += 1;
    });
    if (!inserted) continue;
    group.replaceWith(fragment);
    changed = true;
  }

  if (changed) {
    document.documentElement.dataset.gijonGroupsExpanded = "true";
    // Combined filters already own all filter semantics. Re-run them once now
    // that every exhibition is represented by a normal data-event-id card.
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
}

function scheduleExpand(delay = 0) {
  if (scheduled && delay === 0) return;
  if (delay > 0) {
    setTimeout(() => scheduleExpand(0), delay);
    return;
  }
  scheduled = true;
  requestAnimationFrame(() => { void expandGroups(); });
}

for (const delay of [0, 120, 450, 1000]) scheduleExpand(delay);

new MutationObserver(() => {
  eventsById = new Map();
  scheduleExpand(150);
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

window.addEventListener("pageshow", () => scheduleExpand(80), { passive: true });
