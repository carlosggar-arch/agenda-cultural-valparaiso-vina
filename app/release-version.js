(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v183 adds next-opening guidance and explicit missing event-time fallback.
  const RELEASE = 183;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();