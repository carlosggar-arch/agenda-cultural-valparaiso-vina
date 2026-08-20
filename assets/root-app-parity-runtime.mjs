import { loadRootPublicDataset } from "./root-app-parity-data.mjs?v=20260820-app-parity1";

const nativeFetch = globalThis.fetch.bind(globalThis);

// Start the APP publication pipeline immediately, but do not block installation
// of the root fetch adapter. Independent module scripts may otherwise begin
// loading while a top-level await is still pending.
const publicDatasetPromise = loadRootPublicDataset({ fetchImpl: nativeFetch })
  .then((dataset) => {
    document.documentElement.dataset.rootAppParity = "active";
    return dataset;
  })
  .catch((error) => {
    document.documentElement.dataset.rootAppParity = "fallback";
    console.warn("¡Vivamos! WEB: no se pudo aplicar el pipeline compartido; se usa el dataset base.", error);
    return null;
  });

globalThis.fetch = async (input, init) => {
  let candidate = "";
  if (typeof input === "string" || input instanceof URL) candidate = String(input);
  else if (input && typeof input.url === "string") candidate = input.url;

  try {
    const url = new URL(candidate, globalThis.location.href);
    if (url.pathname.endsWith("/agenda_web.json")) {
      const publicDataset = await publicDatasetPromise;
      if (publicDataset?.events) {
        return new Response(JSON.stringify(publicDataset), {
          status: 200,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
          },
        });
      }
    }
  } catch {}
  return nativeFetch(input, init);
};

function installWebOnlyPresentationState() {
  if (document.querySelector("style[data-root-web-state-fix]")) return;
  const style = document.createElement("style");
  style.dataset.rootWebStateFix = "true";
  style.textContent = `
    .hero-dots,
    .hero-visual figcaption {
      display: none !important;
    }

    .category-shortcut {
      border-radius: .8rem;
      padding: .45rem .35rem;
      transition: background-color .16s ease, box-shadow .16s ease, transform .16s ease;
    }

    .category-shortcut[aria-pressed="true"],
    .category-shortcut.is-selected {
      background: #eef8f7;
      box-shadow: inset 0 0 0 2px var(--teal);
    }

    .category-shortcut[aria-pressed="true"] strong,
    .category-shortcut.is-selected strong {
      color: var(--navy);
    }

    .category-shortcut[aria-pressed="true"] .category-symbol,
    .category-shortcut.is-selected .category-symbol {
      box-shadow: 0 0 0 3px #fffdf8, 0 0 0 5px var(--teal);
      transform: translateY(-1px);
    }
  `;
  document.head.append(style);

  document.querySelectorAll(".hero-dots, .hero-visual figcaption").forEach((node) => node.remove());
}

function syncCategorySelectionState() {
  document.querySelectorAll(".category-shortcut").forEach((button) => {
    button.classList.toggle("is-selected", button.getAttribute("aria-pressed") === "true");
  });
}

function resultCount() {
  const result = document.querySelector("[data-result-line]");
  const match = String(result?.textContent || "").match(/^\s*(\d+)\s+actividades?\b/iu);
  return match ? match[1] : null;
}

function forceCountParity() {
  const total = document.querySelector("[data-total]");
  const count = resultCount();
  if (!total || count === null) return;
  if (total.textContent !== count) total.textContent = count;
}

function installCountParity() {
  let queued = false;
  const sync = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      forceCountParity();
      syncCategorySelectionState();
    });
    requestAnimationFrame(() => {
      forceCountParity();
      syncCategorySelectionState();
    });
  };

  const observer = new MutationObserver(sync);
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["hidden", "aria-pressed"],
  });

  for (const eventName of ["click", "change", "input"]) {
    document.addEventListener(eventName, sync, true);
  }

  // Late renderers on the WEB can finish a few frames after the navigation click.
  // Keep the hero total pinned to the result line during initialisation, then the
  // observer/event hooks above maintain parity for subsequent interactions.
  let checks = 0;
  const initialTimer = setInterval(() => {
    forceCountParity();
    syncCategorySelectionState();
    checks += 1;
    if (checks >= 24) clearInterval(initialTimer);
  }, 250);

  sync();
}

// La estética y el render siguen siendo exclusivamente los de la WEB.
// Los scripts actuales de la WEB se cargan después de este adaptador desde index.html.
installWebOnlyPresentationState();
installCountParity();
