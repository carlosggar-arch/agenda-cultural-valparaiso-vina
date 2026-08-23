(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v201 binds the outer app.js entrypoint cache key to the release so new presentation code cannot stay hidden behind a stale module URL.
  const RELEASE = 201;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();