importScripts("./release-version.js", "./service-worker-assets.generated.js");

const RELEASE = Number(globalThis.__VIVAMOS_RELEASE__);
if (!Number.isInteger(RELEASE) || RELEASE < 1) {
  throw new Error("¡Vivamos!: invalid shared release version");
}
const SHELL_ASSETS = globalThis.__VIVAMOS_SHELL_ASSETS__;
if (!Array.isArray(SHELL_ASSETS) || !SHELL_ASSETS.length) {
  throw new Error("¡Vivamos!: invalid generated shell asset manifest");
}
const CACHE_VERSION = `v${RELEASE}`;
const SHELL_CACHE = `agenda-cultural-shell-${CACHE_VERSION}`;
const DATA_CACHE = `agenda-cultural-data-${CACHE_VERSION}`;

const CITY_REGISTRY_URL = new URL("./cities.json", self.registration.scope).href;
let datasetUrlsPromise = null;

async function datasetUrls() {
  if (!datasetUrlsPromise) {
    datasetUrlsPromise = (async () => {
      try {
        const response = await fetch(CITY_REGISTRY_URL, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const registry = await response.json();
        const urls = new Set((registry.cities || []).map((city) => new URL(city.dataset, self.registration.scope).href));
        if (!urls.size) throw new Error("Empty city registry");
        return urls;
      } catch {
        return new Set([
          new URL("../agenda_web.json", self.registration.scope).href,
          new URL("./data/gijon/agenda_web.json", self.registration.scope).href,
        ]);
      }
    })();
  }
  return datasetUrlsPromise;
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    await cache.addAll(SHELL_ASSETS);
    await self.skipWaiting();
  })());
});

async function warmDatasetCache() {
  const cache = await caches.open(DATA_CACHE);
  const urls = await datasetUrls();
  await Promise.allSettled([...urls].map(async (url) => {
    const request = new Request(url, { headers: { Accept: "application/json" } });
    const response = await fetch(request, { cache: "no-store" });
    if (response.ok) await cache.put(request, response.clone());
  }));
}

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => name.startsWith("agenda-cultural-") && ![SHELL_CACHE, DATA_CACHE].includes(name))
      .map((name) => caches.delete(name)));
    await warmDatasetCache();
    await self.clients.claim();
  })());
});

async function refreshShell(cache, request) {
  try {
    const response = await fetch(request, { cache: "no-store" });
    if (response.ok && new URL(request.url).origin === self.location.origin) {
      await cache.put(request, response.clone());
    }
    return response;
  } catch {
    return null;
  }
}

async function cacheFirstNavigation(request, event) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = (await cache.match(request, { ignoreSearch: true }))
    || (await cache.match("./index.html"))
    || (await cache.match("./"));

  if (cached) {
    event.waitUntil(refreshShell(cache, request).then(() => undefined));
    return cached;
  }

  const response = await refreshShell(cache, request);
  if (response) return response;
  return Response.error();
}

async function networkFirstFreshShell(request) {
  const cache = await caches.open(SHELL_CACHE);
  const response = await refreshShell(cache, request);
  if (response) return response;
  return (await cache.match(request))
    || (await cache.match(request, { ignoreSearch: true }))
    || Response.error();
}

async function cacheFirstShell(request, event) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  if (cached) {
    event.waitUntil(refreshShell(cache, request).then(() => undefined));
    return cached;
  }
  const response = await refreshShell(cache, request);
  if (response) return response;
  return (await cache.match(request, { ignoreSearch: true })) || Response.error();
}

async function fetchAndCacheDataset(cache, request) {
  try {
    const response = await fetch(request, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    await cache.put(request, response.clone());
    return response;
  } catch {
    return null;
  }
}

async function cacheFirstDataset(request, event) {
  const cache = await caches.open(DATA_CACHE);
  const cached = await cache.match(request, { ignoreSearch: true });
  if (cached) {
    event.waitUntil(fetchAndCacheDataset(cache, request).then(() => undefined));
    return cached;
  }

  const network = await fetchAndCacheDataset(cache, request);
  if (network?.ok) return network;
  return new Response(JSON.stringify({ error: "offline_dataset_unavailable" }), {
    status: 503,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const requestUrl = new URL(request.url);
  if (request.mode === "navigate") {
    event.respondWith(cacheFirstNavigation(request, event));
    return;
  }
  if (requestUrl.origin !== self.location.origin) return;
  if (requestUrl.pathname.endsWith("/release-version.js")) {
    event.respondWith(networkFirstFreshShell(request));
    return;
  }
  event.respondWith((async () => {
    const urls = await datasetUrls();
    const supplemental = requestUrl.pathname.endsWith("/supplemental-events.json");
    if (urls.has(requestUrl.href) || supplemental) return cacheFirstDataset(request, event);
    return cacheFirstShell(request, event);
  })());
});
