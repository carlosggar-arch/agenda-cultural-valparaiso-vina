import { referenceNow, selectPlanAhead } from "./plan-ahead-core.mjs?v=20260817";

const DATASET_URL = "./agenda_web.json";
const CITY = "valparaiso";
const LOCALE = "es-CL";

function installStyles() {
  if (document.querySelector("link[data-plan-ahead-styles]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./assets/plan-ahead.css?v=20260817";
  link.dataset.planAheadStyles = "true";
  document.head.append(link);
}

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function dateLabel(date) {
  return new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "short" }).format(date);
}

function deadlineLabel(date) {
  if (!date) return null;
  return `Inscripción hasta ${new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long" }).format(date)}`;
}

function locationLabel(event) {
  const location = event?.location || {};
  return [location.venue, location.city].filter(Boolean).filter((value, index, rows) => rows.indexOf(value) === index).join(" · ");
}

function eventPage(event) {
  return `./evento/${CITY}/${encodeURIComponent(String(event.id))}/`;
}

function mediaNode(event) {
  const media = document.createElement("div");
  media.className = "plan-ahead-media";
  const src = event?.image?.relevance === "generic_schedule" ? null : safeUrl(event?.image?.url);
  if (src) {
    const image = document.createElement("img");
    image.src = src;
    image.alt = String(event?.image?.alt || event?.title || "Imagen de la actividad");
    image.loading = "lazy";
    image.decoding = "async";
    image.addEventListener("error", () => {
      media.replaceChildren(Object.assign(document.createElement("span"), { className: "plan-ahead-fallback", textContent: "✦" }));
    }, { once: true });
    media.append(image);
  } else {
    media.append(Object.assign(document.createElement("span"), { className: "plan-ahead-fallback", textContent: "✦" }));
  }
  return media;
}

function cardNode(candidate) {
  const { event, action, badges, startsAt, deadline } = candidate;
  const article = document.createElement("article");
  article.className = "plan-ahead-card";
  article.append(mediaNode(event));

  const body = document.createElement("div");
  body.className = "plan-ahead-body";
  const badgeRow = document.createElement("div");
  badgeRow.className = "plan-ahead-badges";
  for (const badge of badges) {
    const node = document.createElement("span");
    node.className = `plan-ahead-badge${badge === "Cupos limitados" ? " plan-ahead-badge--limited" : ""}`;
    node.textContent = badge;
    badgeRow.append(node);
  }
  body.append(badgeRow);

  const title = document.createElement("h3");
  title.textContent = event?.title || "Actividad cultural";
  body.append(title);

  const meta = document.createElement("p");
  meta.className = "plan-ahead-meta";
  meta.textContent = [dateLabel(startsAt), locationLabel(event)].filter(Boolean).join(" · ");
  body.append(meta);

  const deadlineText = deadlineLabel(deadline);
  if (deadlineText) {
    const deadlineNode = document.createElement("p");
    deadlineNode.className = "plan-ahead-deadline";
    deadlineNode.textContent = deadlineText;
    body.append(deadlineNode);
  }

  const actions = document.createElement("div");
  actions.className = "plan-ahead-actions";
  const primary = document.createElement("a");
  primary.className = "plan-ahead-action plan-ahead-action--primary";
  primary.href = action.url;
  primary.target = "_blank";
  primary.rel = "noopener noreferrer";
  primary.textContent = `${action.actionLabel} ↗`;
  actions.append(primary);

  const detail = document.createElement("a");
  detail.className = "plan-ahead-action plan-ahead-action--secondary";
  detail.href = eventPage(event);
  detail.textContent = "Ver ficha";
  actions.append(detail);
  body.append(actions);
  article.append(body);
  return article;
}

function sectionNode(candidates) {
  const section = document.createElement("section");
  section.className = "plan-ahead-section";
  section.dataset.planAhead = "true";
  section.dataset.city = CITY;
  section.setAttribute("aria-labelledby", "plan-ahead-title");

  const inner = document.createElement("div");
  inner.className = "plan-ahead-inner";
  const heading = document.createElement("header");
  heading.className = "plan-ahead-heading";
  const copy = document.createElement("div");
  copy.className = "plan-ahead-heading-copy";
  copy.innerHTML = '<p class="plan-ahead-eyebrow">Organízate con tiempo</p><h2 id="plan-ahead-title">Planifica con anticipación</h2><p>Actividades de las próximas 2–8 semanas que ya requieren entradas, inscripción o reserva previa.</p>';
  const windowBadge = document.createElement("span");
  windowBadge.className = "plan-ahead-window";
  windowBadge.textContent = "Próximas 2–8 semanas";
  heading.append(copy, windowBadge);

  const grid = document.createElement("div");
  grid.className = "plan-ahead-grid";
  for (const candidate of candidates) grid.append(cardNode(candidate));
  inner.append(heading, grid);
  section.append(inner);
  return section;
}

async function start() {
  installStyles();
  let payload;
  try {
    const response = await fetch(DATASET_URL, { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    payload = await response.json();
  } catch { return; }

  const candidates = selectPlanAhead(payload?.events || [], { now: referenceNow(payload), minDays: 14, maxDays: 56, limit: 6 });
  document.querySelector("[data-plan-ahead]")?.remove();
  if (!candidates.length) return;

  const anchor = document.querySelector(".category-section") || document.querySelector(".featured-section") || document.querySelector(".status-panel");
  if (!anchor) return;
  anchor.insertAdjacentElement("afterend", sectionNode(candidates));
}

start();
