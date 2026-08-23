import { loadRootPublicDataset } from "./root-app-parity-data.mjs?v=20260823-selection1";

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

// La estética y el render siguen siendo exclusivamente los de la WEB.
// Los scripts actuales de la WEB se cargan después de este adaptador desde index.html.
installCountParity();
