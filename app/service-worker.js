importScripts("./release-version.js");

const RELEASE = Number(globalThis.__VIVAMOS_RELEASE__);
if (!Number.isInteger(RELEASE) || RELEASE < 1) {
  throw new Error("¡Vivamos!: invalid shared release version");
}

const CACHE_VERSION = `v${RELEASE}`;
const SHELL_CACHE = `agenda-cultural-shell-${CACHE_VERSION}`;
const DATA_CACHE = `agenda-cultural-data-${CACHE_VERSION}`;
const DATA_NETWORK_BUDGET_MS = 700;

// Keep the installation small and reliable. The rest of the same-origin shell
// is cached on first use by cacheFirstShell().
const CORE_SHELL = [
  "./",
  "./index.html",
  "./release-version.js",
  "./app.css",
  "./app.js",
  "./app-core.js",
  "./data-pipeline.js",
  "./startup-stability.js",
  "./render-lifecycle.js",
  "./cities.json",
  "../assets/city-registry.mjs",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    await cache.addAll(CORE_SHELL);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => name.startsWith("agenda-cultural-") && ![SHELL_CACHE, DATA_CACHE].includes(name))
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

function timeout(ms) {
  return new Promise((resolve) => setTimeout(() => resolve(null), ms));
}

async function refreshCache(cache, request) {
  try {
    const response = await fetch(request, { cache: "no-cache" });
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch {
    return null;
  }
}

async function cacheFirstShell(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  if (cached) {
    // Do not block rendering on validation. Refresh the exact URL in the background.
    void refreshCache(cache, request);
    return cached;
  }

  const response = await fetch(request);
  if (response.ok) await cache.put(request, response.clone());
  return response;
}

async function fastNavigation(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = (await cache.match(request, { ignoreSearch: true }))
    || (await cache.match("./index.html"))
    || (await cache.match("./"));

  if (cached) {
    void refreshCache(cache, request);
    return cached;
  }

  return fetch(request);
}

async function boundedFreshData(request) {
  const cache = await caches.open(DATA_CACHE);
  const cached = await cache.match(request, { ignoreSearch: true });
  const networkPromise = refreshCache(cache, request);

  // Prefer fresh data when the network is quick, but never make a returning
  // visitor wait several seconds when a valid local copy already exists.
  if (cached) {
    const quickNetwork = await Promise.race([
      networkPromise,
      timeout(DATA_NETWORK_BUDGET_MS),
    ]);
    if (quickNetwork?.ok) return quickNetwork;
    return cached;
  }

  const network = await networkPromise;
  if (network?.ok) return network;
  return new Response(JSON.stringify({ error: "offline_dataset_unavailable" }), {
    status: 503,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function isRuntimeData(url) {
  if (!url.pathname.endsWith(".json")) return false;
  return url.pathname.endsWith("/agenda_web.json")
    || url.pathname.endsWith("/supplemental-events.json")
    || url.pathname.endsWith("/cities.json");
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(fastNavigation(request));
    return;
  }

  if (isRuntimeData(url)) {
    event.respondWith(boundedFreshData(request));
    return;
  }

  event.respondWith(cacheFirstShell(request));
});
