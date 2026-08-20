import { loadRootPublicDataset } from "./root-app-parity-data.mjs?v=20260820-app-parity1";

const nativeFetch = globalThis.fetch.bind(globalThis);
let publicDataset = null;

try {
  publicDataset = await loadRootPublicDataset({ fetchImpl: nativeFetch });
  document.documentElement.dataset.rootAppParity = "active";
} catch (error) {
  console.warn("¡Vivamos! WEB: no se pudo aplicar el pipeline compartido; se usa el dataset base.", error);
  document.documentElement.dataset.rootAppParity = "fallback";
}

if (publicDataset?.events) {
  const serialized = JSON.stringify(publicDataset);
  globalThis.fetch = async (input, init) => {
    let candidate = "";
    if (typeof input === "string" || input instanceof URL) candidate = String(input);
    else if (input && typeof input.url === "string") candidate = input.url;

    try {
      const url = new URL(candidate, globalThis.location.href);
      if (url.pathname.endsWith("/agenda_web.json")) {
        return new Response(serialized, {
          status: 200,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store",
          },
        });
      }
    } catch {}
    return nativeFetch(input, init);
  };
}

// La estética y el render siguen siendo exclusivamente los de la WEB.
await import("./agenda.js?v=20260820-app-parity1");
await import("./web-event-enhancements.js?v=20260820-webparity5");

function installCountParity() {
  const total = document.querySelector("[data-total]");
  const result = document.querySelector("[data-result-line]");
  if (!total || !result) return;

  let queued = false;
  const sync = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      const match = String(result.textContent || "").match(/^\s*(\d+)\s+actividades?\b/iu);
      if (match && total.textContent !== match[1]) total.textContent = match[1];
    });
  };

  const observer = new MutationObserver(sync);
  observer.observe(result, { childList: true, subtree: true, characterData: true });
  observer.observe(total, { childList: true, subtree: true, characterData: true });
  sync();
}

installCountParity();
