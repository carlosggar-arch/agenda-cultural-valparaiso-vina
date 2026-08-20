import "./startup-stability.js?v=20260819-startup2";
import "./render-lifecycle.js?v=20260819-lifecycle1";

// The core is intentionally a dynamic import: the watchdog above must execute
// even if the core module graph fails to load or evaluate.
const { coreReady } = await import("./app-core.js?v=20260820-recovery1");

// Deferred-module compatibility marker kept aligned with the single runtime URL.
// import "./schedule-display.js?v=20260820-today1";
// The equivalent data path now lives in data-pipeline.js and is published once
// through agenda-runtime-state.mjs for all presentation consumers.

const IMAGE_QUALITY_GUARD = "./image-quality-guard.js?v=20260820-images3";
const OPTIONAL_MODULES = [
  "./temporal-priority.js?v=20260819-temporal3",
  "./static-exhibition-groups.js?v=20260818-staticgroups1",
  "./multievent-layout-fix.js?v=20260819-multievent1",
  "./schedule-display.js?v=20260820-today1",
  "./footer-credit.js?v=20260818-footer3",
  "./community-source.js?v=20260818-feedback3",
  "./participation-footer.js?v=20260819-feedback7",
];

// Gijon keeps the stable core renderer. Combined filters own its temporal
// selection and the heavier Valpo/Viña presentation modules remain out of this
// runtime. A clean city reload guarantees that these module sets never mix.
const GIJON_DEFERRED_MODULES = new Set([
  "./temporal-priority.js?v=20260819-temporal3",
  "./static-exhibition-groups.js?v=20260818-staticgroups1",
  "./multievent-layout-fix.js?v=20260819-multievent1",
  "./schedule-display.js?v=20260820-today1",
]);
const IS_GIJON = String(document.documentElement.dataset.city || "") === "gijon";
if (IS_GIJON) {
  for (let index = OPTIONAL_MODULES.length - 1; index >= 0; index -= 1) {
    if (GIJON_DEFERRED_MODULES.has(OPTIONAL_MODULES[index])) OPTIONAL_MODULES.splice(index, 1);
  }
  OPTIONAL_MODULES.push("./gijon-card-images.js?v=20260819-images1");
  document.documentElement.dataset.gijonStableRuntime = "true";
} else {
  // app.js is the single owner of content presentation. These modules consume
  // the normalized runtime snapshot and react to bounded agenda lifecycle events;
  // none installs a body-wide subtree observer or re-fetches the raw dataset.
  OPTIONAL_MODULES.push(
    "./card-experience.js?v=20260819-runtime1",
    "./card-image-fallback.js?v=20260819-runtime1",
    "./public-presentation-guard.js?v=20260820-text1",
    "./exhibition-hours.js?v=20260820-hours5",
  );
}

function ensureSourcesFallbackLink() {
  const footer = document.querySelector("body > footer");
  if (!footer) return null;
  const dynamic = footer.querySelector("[data-sources-toggle]");
  if (dynamic) return dynamic;

  let fallback = footer.querySelector("[data-sources-fallback]");
  if (!fallback) {
    fallback = document.createElement("a");
    fallback.href = "../fuentes.html";
    fallback.className = "sources-toggle sources-fallback";
    fallback.dataset.sourcesFallback = "";
    fallback.textContent = "Fuentes";
    fallback.setAttribute("aria-label", "Ver todas las fuentes de la agenda");
    const version = footer.querySelector("[data-app-version]");
    if (version) footer.insertBefore(fallback, version);
    else footer.append(fallback);
  }
  footer.classList.add("vivamos-footer--with-sources");
  return fallback;
}

function placeSourcesButtonInFooter() {
  const footer = document.querySelector("body > footer");
  const button = footer?.querySelector("[data-sources-toggle]");
  if (!footer || !button) return false;

  footer.querySelector("[data-sources-fallback]")?.remove();
  const version = footer.querySelector("[data-app-version]");
  if (version && button.nextElementSibling !== version) footer.insertBefore(button, version);
  footer.classList.add("vivamos-footer--with-sources");

  const styleId = "vivamos-footer-sources-layout";
  if (!document.getElementById(styleId)) {
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .vivamos-footer.vivamos-footer--with-sources {
        grid-template-columns: auto minmax(0, 1fr) auto auto auto;
      }
      .vivamos-footer .sources-toggle {
        display:inline-flex;
        align-items:center;
        justify-content:center;
        min-height:2.35rem;
        padding:.5rem .85rem;
        border:1px solid rgba(255,255,255,.72);
        border-radius:999px;
        background:#fff;
        color:#174f46;
        font:inherit;
        font-weight:850;
        line-height:1;
        text-decoration:none;
        cursor:pointer;
      }
      .vivamos-footer .sources-toggle:hover,
      .vivamos-footer .sources-toggle:focus-visible {
        border-color:#f4d16d;
        background:#f4d16d;
        color:#103c36;
        outline:2px solid rgba(255,255,255,.72);
        outline-offset:2px;
      }
      @media (max-width: 900px) {
        .vivamos-footer.vivamos-footer--with-sources {
          grid-template-columns: 1fr auto;
        }
        .vivamos-footer.vivamos-footer--with-sources .sources-toggle {
          grid-column: 1;
          width: max-content;
        }
      }
    `;
    document.head.append(style);
  }
  return true;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function loadImageQualityGuard() {
  if (IS_GIJON) return;
  const delays = [0, 250, 1000];
  let lastError = null;
  for (const delay of delays) {
    if (delay) await wait(delay);
    try {
      await import(IMAGE_QUALITY_GUARD);
      document.documentElement.dataset.imageQualityGuard = "ready";
      return;
    } catch (error) {
      lastError = error;
    }
  }
  document.documentElement.dataset.imageQualityGuard = "failed";
  console.warn("¡Vivamos!: no se pudo cargar la protección de imágenes tras varios intentos", lastError);
}

async function loadOptionalEnhancements() {
  if (!IS_GIJON) void loadImageQualityGuard();

  const results = await Promise.allSettled(OPTIONAL_MODULES.map((module) => import(module)));
  results.forEach((result, index) => {
    if (result.status === "rejected") console.warn(`¡Vivamos!: mejora opcional omitida (${OPTIONAL_MODULES[index]})`, result.reason);
  });

  // The public source catalogue must always be reachable. Install a normal
  // link first; if the richer in-page source toggle loads successfully, it
  // replaces this fallback. This avoids losing Fuentes because of an optional
  // module failure, missing source section, cache mismatch or footer timing.
  ensureSourcesFallbackLink();
  try {
    await import("./sources-toggle.js?v=20260820-sources2");
  } catch (error) {
    console.warn("¡Vivamos!: vista integrada de fuentes omitida; se conserva el enlace de catálogo", error);
  }
  if (!placeSourcesButtonInFooter()) ensureSourcesFallbackLink();
}

await coreReady;
void loadOptionalEnhancements();

let exhibitionOrderQueued = false;

function defaultFiltersAreNeutral() {
  const when = document.querySelector('[data-combined-when] [data-filter-value].active')?.dataset?.filterValue || "todos";
  const area = document.querySelector('[data-combined-area] [data-filter-value].active')?.dataset?.filterValue || "todos";
  const categories = document.querySelectorAll('[data-combined-category-filters] [data-combined-category].active').length;
  const query = String(document.querySelector('[data-smart-search]')?.value || "").trim();
  const from = String(document.querySelector('[data-date-from]')?.value || "").trim();
  const to = String(document.querySelector('[data-date-to]')?.value || "").trim();
  return when === "todos" && area === "todos" && categories === 0 && !query && !from && !to;
}

function placeExhibitionsLast() {
  exhibitionOrderQueued = false;
  if (!defaultFiltersAreNeutral()) return;
  const grid = document.querySelector('[data-dated-grid]');
  if (!grid) return;
  const cards = [...grid.children].filter((node) => node.classList?.contains("event-card"));
  if (cards.length < 2) return;
  const regular = cards.filter((card) => card.dataset.category !== "exposiciones");
  const exhibitions = cards.filter((card) => card.dataset.category === "exposiciones");
  if (!regular.length || !exhibitions.length) return;
  const ordered = [...regular, ...exhibitions];
  if (ordered.every((card, index) => card === cards[index])) return;
  const fragment = document.createDocumentFragment();
  for (const card of ordered) fragment.append(card);
  grid.append(fragment);
}

function scheduleExhibitionOrder() {
  if (exhibitionOrderQueued) return;
  exhibitionOrderQueued = true;
  queueMicrotask(placeExhibitionsLast);
}

// The Gijon stable path intentionally avoids even this small ordering observer.
// Valpo/Viña keeps one grid-level child-list observer; descendant/text/image
// changes are ignored, so presentation enhancers cannot recursively wake it.
if (!IS_GIJON) {
  const datedGrid = document.querySelector('[data-dated-grid]');
  if (datedGrid) {
    new MutationObserver(scheduleExhibitionOrder).observe(datedGrid, { childList: true });
  }
  document.addEventListener("click", (event) => {
    if (event.target.closest('[data-filter-value], [data-combined-category], [data-filter-clear]')) scheduleExhibitionOrder();
  });
  document.addEventListener("input", (event) => {
    if (event.target.matches('[data-smart-search], [data-date-from], [data-date-to]')) scheduleExhibitionOrder();
  });
  scheduleExhibitionOrder();
}
