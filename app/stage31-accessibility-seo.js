const SITE_BASE = "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina";

const CITY_SEO = Object.freeze({
  valparaiso: {
    title: "Agenda Cultural Valparaíso / Viña del Mar · ¡Vivamos!",
    description: "Actividades culturales revisadas de Valparaíso y Viña del Mar: qué hacer hoy, este fin de semana y próximos panoramas.",
    canonical: `${SITE_BASE}/`,
    locale: "es_CL",
  },
  gijon: {
    title: "Agenda Cultural Gijón / Xixón · ¡Vivamos!",
    description: "Actividades culturales revisadas de Gijón / Xixón: qué hacer hoy, este fin de semana y próximos eventos.",
    canonical: `${SITE_BASE}/gijon/`,
    locale: "es_ES",
  },
});

function ensureStylesheet() {
  if (document.querySelector("link[data-stage31-accessibility]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./stage31-accessibility.css?v=20260817";
  link.dataset.stage31Accessibility = "true";
  document.head.append(link);
}

function ensureMeta(selector, attributes) {
  let node = document.head.querySelector(selector);
  if (!node) {
    node = document.createElement(attributes.tag || "meta");
    document.head.append(node);
  }
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "tag") continue;
    node.setAttribute(name, value);
  }
  return node;
}

function applyCitySeo() {
  const cityId = document.documentElement.dataset.city || "valparaiso";
  const seo = CITY_SEO[cityId] || CITY_SEO.valparaiso;
  document.title = seo.title;
  ensureMeta('meta[name="description"]', { name: "description", content: seo.description });
  ensureMeta('meta[name="robots"]', { name: "robots", content: "index,follow,max-image-preview:large" });
  ensureMeta('link[rel="canonical"]', { tag: "link", rel: "canonical", href: seo.canonical });
  ensureMeta('meta[property="og:type"]', { property: "og:type", content: "website" });
  ensureMeta('meta[property="og:site_name"]', { property: "og:site_name", content: "¡Vivamos! · Agenda Cultural" });
  ensureMeta('meta[property="og:locale"]', { property: "og:locale", content: seo.locale });
  ensureMeta('meta[property="og:title"]', { property: "og:title", content: seo.title });
  ensureMeta('meta[property="og:description"]', { property: "og:description", content: seo.description });
  ensureMeta('meta[property="og:url"]', { property: "og:url", content: seo.canonical });
  ensureMeta('meta[name="twitter:card"]', { name: "twitter:card", content: "summary" });
  ensureMeta('meta[name="twitter:title"]', { name: "twitter:title", content: seo.title });
  ensureMeta('meta[name="twitter:description"]', { name: "twitter:description", content: seo.description });
}

const backdrop = document.querySelector("[data-chooser-backdrop]");
const chooser = document.querySelector("[data-chooser]");
const closeButton = document.querySelector("[data-chooser-close]");
const citySwitch = document.querySelector("[data-city-switch]");
const status = document.querySelector("[data-status]");
const main = document.querySelector("main");
const filterSummary = document.querySelector("[data-filter-summary]");
const backgroundNodes = [...document.body.children].filter((node) =>
  node !== backdrop && !["SCRIPT", "STYLE", "LINK"].includes(node.tagName),
);
let returnFocus = null;
let modalOpen = false;

function focusableWithinChooser() {
  if (!chooser) return [];
  return [...chooser.querySelectorAll('a[href], button:not([disabled]):not([hidden]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
    .filter((node) => !node.hidden && node.getClientRects().length > 0);
}

function openModalA11y() {
  if (!backdrop || !chooser || backdrop.hidden || modalOpen) return;
  modalOpen = true;
  if (!chooser.contains(document.activeElement)) returnFocus = document.activeElement;
  backgroundNodes.forEach((node) => { node.inert = true; });
  document.body.classList.add("has-modal-dialog");
  citySwitch?.setAttribute("aria-expanded", "true");
  const focusables = focusableWithinChooser();
  const preferred = closeButton && !closeButton.hidden ? closeButton : focusables[0];
  window.requestAnimationFrame(() => preferred?.focus());
}

function closeModalA11y() {
  if (!modalOpen) return;
  modalOpen = false;
  backgroundNodes.forEach((node) => { node.inert = false; });
  document.body.classList.remove("has-modal-dialog");
  citySwitch?.setAttribute("aria-expanded", "false");
  const target = returnFocus instanceof HTMLElement && document.body.contains(returnFocus) ? returnFocus : citySwitch;
  returnFocus = null;
  window.requestAnimationFrame(() => target?.focus());
}

function syncModalState() {
  if (!backdrop) return;
  if (backdrop.hidden) closeModalA11y();
  else openModalA11y();
}

function syncBusyState() {
  if (!main || !status) return;
  main.setAttribute("aria-busy", status.hidden ? "false" : "true");
}

function prepareDialogSemantics() {
  if (!chooser || !citySwitch) return;
  chooser.id ||= "city-chooser";
  citySwitch.setAttribute("aria-controls", chooser.id);
  citySwitch.setAttribute("aria-expanded", backdrop?.hidden === false ? "true" : "false");
  const description = chooser.querySelector("h2 + p");
  if (description) {
    description.id ||= "city-chooser-description";
    chooser.setAttribute("aria-describedby", description.id);
  }
}

function handleModalKeys(event) {
  if (!modalOpen || !chooser) return;
  if (event.key === "Escape") {
    if (closeButton && !closeButton.hidden) {
      event.preventDefault();
      event.stopPropagation();
      closeButton.click();
    } else {
      event.preventDefault();
    }
    return;
  }
  if (event.key !== "Tab") return;
  const focusables = focusableWithinChooser();
  if (!focusables.length) {
    event.preventDefault();
    chooser.focus();
    return;
  }
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

ensureStylesheet();
prepareDialogSemantics();
status?.setAttribute("aria-atomic", "true");
filterSummary?.setAttribute("aria-atomic", "true");
chooser?.setAttribute("tabindex", "-1");

new MutationObserver(applyCitySeo).observe(document.documentElement, {
  attributes: true,
  attributeFilter: ["data-city"],
});
if (backdrop) new MutationObserver(syncModalState).observe(backdrop, { attributes: true, attributeFilter: ["hidden"] });
if (status) new MutationObserver(syncBusyState).observe(status, { attributes: true, attributeFilter: ["hidden"] });
document.addEventListener("keydown", handleModalKeys, true);

applyCitySeo();
syncModalState();
syncBusyState();
