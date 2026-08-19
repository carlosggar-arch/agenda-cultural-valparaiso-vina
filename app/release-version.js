(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v116 adds conservative multi-city temporal priority while preserving the
  // v115 shared schedule formatter and its corrected exhibition schedules.
  const RELEASE = 116;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
