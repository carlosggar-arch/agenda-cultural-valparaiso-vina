import { referenceNow, selectPlanAhead } from "../assets/plan-ahead-core.mjs?v=20260817";

const CONFIG = Object.freeze({
  valparaiso: { dataset: "../agenda_web.json", locale: "es-CL" },
  gijon: { dataset: "./data/gijon/agenda_web.json", locale: "es-ES" },
});

let renderToken = 0;

function installStyles() {
  if (document.querySelector("link[data-plan-ahead-styles]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "../assets/plan-ahead.css?v=20260817-compact";
  link.dataset.planAheadStyles = "true";
  document.head.append(link);
}

function cityId() {
  return CONFIG[document.documentElement.dataset.city] ? document.documentElement.dataset.city : "valparaiso";
}

function dateLabel(date, locale) {
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(date);
}

function deadlineLabel(date, locale) {
  if (!date) return null;
  return `Inscripción hasta ${new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(date)}`;
}

function locationLabel(event) {
  const location = event?.location || {};
  return [location.venue, location.city]
    .filter(Boolean)
    .filter((value, index, rows) => rows.indexOf(value) === index)
    .join(" · ");
}

function rowNode(candidate, locale) {
  const { event, action, startsAt, deadline } = candidate;
  const row = document.createElement("article");
  row.className = "plan-ahead-row";
  row.dataset.eventId = String(event?.id || "");

  const when = document.createElement("time");
  when.className = "plan-ahead-date";
  when.dateTime = startsAt.toISOString();
  when.textContent = dateLabel(startsAt, locale);

  const main = document.createElement("div");
  main.className = "plan-ahead-row-main";
  const title = document.createElement("strong");
  title.textContent = event?.title || "Actividad";
  main.append(title);

  const details = [locationLabel(event), deadlineLabel(deadline, locale)].filter(Boolean);
  if (details.length) {
    const meta = document.createElement("small");
    meta.textContent = details.join(" · ");
    main.append(meta);
  }

  const primary = document.createElement("a");
  primary.className = "plan-ahead-action";
  primary.href = action.url;
  primary.target = "_blank";
  primary.rel = "noopener noreferrer";
  primary.textContent = `${action.actionLabel} ↗`;

  row.append(when, main, primary);
  return row;
}

function sectionNode(candidates, city, locale) {
  const section = document.createElement("section");
  section.className = "plan-ahead-section";
  section.dataset.planAhead = "true";
  section.dataset.city = city;
  section.setAttribute("aria-label", "Planifica con anticipación");

  const disclosure = document.createElement("details");
  disclosure.className = "plan-ahead-disclosure";

  const summary = document.createElement("summary");
  summary.className = "plan-ahead-summary";

  const icon = document.createElement("span");
  icon.className = "plan-ahead-summary-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "🎟";

  const title = document.createElement("strong");
  title.className = "plan-ahead-summary-title";
  title.textContent = "Planifica con anticipación";

  const count = document.createElement("span");
  count.className = "plan-ahead-summary-count";
  count.textContent = `${candidates.length} ${candidates.length === 1 ? "actividad" : "actividades"} con entrada, inscripción o reserva`;

  const chevron = document.createElement("span");
  chevron.className = "plan-ahead-summary-chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "›";

  summary.append(icon, title, count, chevron);

  const list = document.createElement("div");
  list.className = "plan-ahead-list";
  for (const candidate of candidates) list.append(rowNode(candidate, locale));

  disclosure.append(summary, list);
  section.append(disclosure);
  return section;
}

async function render() {
  installStyles();
  const token = ++renderToken;
  const city = cityId();
  const config = CONFIG[city];
  let payload;
  try {
    const response = await fetch(config.dataset, { headers: { Accept: "application/json" }, cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
  } catch {
    if (token === renderToken) document.querySelector("[data-plan-ahead]")?.remove();
    return;
  }
  if (token !== renderToken || city !== cityId()) return;

  const candidates = selectPlanAhead(payload?.events || [], { now: referenceNow(payload), minDays: 14, maxDays: 56, limit: 6 });
  document.querySelector("[data-plan-ahead]")?.remove();
  if (!candidates.length) return;

  const agenda = document.querySelector(".agenda");
  if (!agenda) return;
  agenda.insertAdjacentElement("beforebegin", sectionNode(candidates, city, config.locale));
}

new MutationObserver((mutations) => {
  if (mutations.some((mutation) => mutation.attributeName === "data-city")) render();
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-city"] });

render();