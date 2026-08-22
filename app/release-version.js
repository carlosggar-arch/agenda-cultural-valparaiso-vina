(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v187 shows the next valid venue opening when an exhibition is closed on the viewed day.
  const RELEASE = 187;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
