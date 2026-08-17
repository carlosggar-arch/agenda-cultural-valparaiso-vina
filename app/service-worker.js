const CACHE_VERSION = "v24";
const SHELL_CACHE = `agenda-cultural-shell-${CACHE_VERSION}`;
const DATA_CACHE = `agenda-cultural-data-${CACHE_VERSION}`;

const SHELL_ASSETS = [
  "./",
  "./index.html",
  "./app.css",
  "./city-header.css",
  "./header-redesign.css",
  "./app.js",
  "./contextual-filters.js",
  "./pwa.js",
  "./vivamos-brand.js",
  "./header-redesign.js",
  "./density-polish.js",
  "./card-experience.js",
  "./schedule-display.js",
  "./event-detail.js",
  "./card-experience.css",
  "./card-image-fallback.js",
  "./compact-top.js",
  "./gijon-visual-reference.js",
  "./lean-filters.js",
  "./sources-toggle.js",
  "./community-source.js",
  "./community-source.css",
  "./proponer-fuente.html",
  "./proponer-fuente.js",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./illustrations/valparaiso-header.svg",
  "./illustrations/gijon-header.svg",
  "../assets/event-media-layout.css",
  "../assets/event-schedule-display.mjs",
  "../assets/categoria-cine.jpg",
  "../assets/categoria-cultura.jpg",
  "../assets/categoria-deportes.jpg",
  "../assets/categoria-exposiciones.jpg",
  "../assets/categoria-gastronomia.jpg",
  "../assets/categoria-musica.jpg",
  "../assets/categoria-naturaleza.jpg",
  "../assets/categoria-talleres.jpg",
  "../assets/categoria-teatro.jpg",
];

const DATASET_URLS = new Set([
  new URL("../agenda_web.json", self.registration.scope).href,
  new URL("./data/gijon/agenda_web.json", self.registration.scope).href,
]);

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    await cache.addAll(SHELL_ASSETS);
    await self.skipWaiting();
  })());
});

async function refreshOpenWindows() {
  const scopeUrl = new URL(self.registration.scope);
  const windowClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  await Promise.all(windowClients.map(async (client) => {
    try {
      const clientUrl = new URL(client.url);
      if (clientUrl.origin !== scopeUrl.origin || !clientUrl.pathname.startsWith(scopeUrl.pathname)) return;
      await client.navigate(client.url);
    } catch {
      // A closed or non-navigable client must not block service-worker activation.
    }
  }));
}

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names
      .filter((name) => name.startsWith("agenda-cultural-") && ![SHELL_CACHE, DATA_CACHE].includes(name))
      .map((name) => caches.delete(name)));
    await self.clients.claim();
    await refreshOpenWindows();
  })());
});

async function networkFirstNavigation(request) {
  try {
    return await fetch(request, { cache: "no-store" });
  } catch {
    return (await caches.match(request, { ignoreSearch: true }))
      || (await caches.match("./index.html"))
      || (await caches.match("./"))
      || Response.error();
  }
}

async function networkFirstShell(request) {
  const cache = await caches.open(SHELL_CACHE);
  try {
    const response = await fetch(request, { cache: "no-store" });
    if (response.ok && new URL(request.url).origin === self.location.origin) {
      await cache.put(request, response.clone());
    }
    return response;
  } catch {
    return (await cache.match(request, { ignoreSearch: true })) || Response.error();
  }
}

async function networkFirstDataset(request) {
  const cache = await caches.open(DATA_CACHE);

  try {
    const response = await fetch(request, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    await cache.put(request, response.clone());

    const cachedRequests = await cache.keys();
    await Promise.all(cachedRequests
      .filter((cachedRequest) => cachedRequest.url !== request.url)
      .map((cachedRequest) => cache.delete(cachedRequest)));

    return response;
  } catch {
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;

    return new Response(JSON.stringify({ error: "offline_dataset_unavailable" }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const requestUrl = new URL(request.url);

  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  if (DATASET_URLS.has(requestUrl.href)) {
    event.respondWith(networkFirstDataset(request));
    return;
  }

  if (requestUrl.origin === self.location.origin) {
    event.respondWith(networkFirstShell(request));
  }
});