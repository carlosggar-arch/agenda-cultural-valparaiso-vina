(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v119 makes the shared schedule formatter authoritative across standalone
  // cards, grouped exhibitions and event details, and removes all-day sentinels.
  const RELEASE = 119;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
