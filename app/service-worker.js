importScripts("./release-version.js");

const RELEASE = Number(globalThis.__VIVAMOS_RELEASE__);
if (!Number.isInteger(RELEASE) || RELEASE < 1) {
  throw new Error("¡Vivamos!: invalid shared release version");
}
const CACHE_VERSION = `v${RELEASE}`;
const SHELL_CACHE = `agenda-cultural-shell-${CACHE_VERSION}`;
const DATA_CACHE = `agenda-cultural-data-${CACHE_VERSION}`;

const SHELL_ASSETS = [
  "./",
  "./index.html",
  "./release-version.js",
  "./app.css",
  "./combined-filters.css",
  "./city-header.css",
  "./compact-top.css",
  "./header-redesign.css?v=20260817-brandicon1",
  "./mobile-experience.css?v=20260817-topcontrols4",
  "./share-qr.css",
  "./stage31-accessibility.css",
  "../assets/usage-analytics.js?v=20260817-stage32",
  "./app.js",
  "./app-core.js",
  "./category-normalizer.js",
  "./public-category-rules.mjs",
  "./exhibition-venue-grouping.js",
  "./exhibition-gallery.js",
  "./exhibition-gallery.css",
  "./exhibition-compact-loader.js?v=20260818-compact9",
  "./exhibition-compact.js?v=20260818-compact9",
  "./exhibition-compact.css?v=20260818-compact8",
  "./exhibition-hours.js?v=20260818-hours2",
  "./presentation-normalizer.js",
  "./public-presentation-guard.js",
  "./public-presentation-rules.mjs",
  "./footer-credit.js",
  "./cities.json",
  "./city-first-run.js",
  "./combined-filters-bootstrap.js",
  "./combined-filters.js",
  "./combined-filters-polish.js",
  "./pwa.js?v=20260818-feedback4",
  "./mobile-experience.js?v=20260817-topcontrols4",
  "./share-qr.js",
  "./stage31-accessibility-seo.js",
  "./plan-ahead.js",
  "./favorites.js",
  "./mis-planes.html",
  "./vivamos-brand.js",
  "./header-redesign.js?v=20260817-brandicon2",
  "./density-polish.js",
  "./card-experience.js",
  "./schedule-display.js",
  "./gijon-venue-hours.js",
  "./event-detail.js",
  "./card-experience.css",
  "./card-image-fallback.js",
  "./compact-top.js",
  "./gijon-visual-reference.js",
  "./sources-toggle.js",
  "./community-source.js",
  "./community-source.css?v=20260818-feedback2",
  "./participation-footer.js?v=20260818-feedback4",
  "./proponer-fuente.html",
  "./proponer-fuente.js",
  "./manifest.webmanifest",
  "./icons/icon.svg",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/share-qr-app.svg",
  "./illustrations/valparaiso-header.svg",
  "./illustrations/gijon-header.svg",
  "../assets/event-media-layout.css",
  "../assets/event-schedule-display.mjs",
  "../assets/plan-ahead-core.mjs",
  "../assets/plan-ahead.css",
  "../assets/city-registry.mjs",
  "../assets/favorites-core.mjs",
  "../assets/favorites-view.mjs",
  "../assets/favorites-reminders.mjs",
  "../assets/favorites.css",
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
    if (response.ok && new URL(request.url).origin === self.location.origin) await cache.put(request, response.clone());
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
  if (requestUrl.origin !== self.location.origin) return;
  event.respondWith((async () => {
    const urls = await datasetUrls();
    if (urls.has(requestUrl.href)) return networkFirstDataset(request);
    return networkFirstShell(request);
  })());
});
