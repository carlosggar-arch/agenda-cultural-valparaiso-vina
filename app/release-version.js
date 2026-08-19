(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v133 keeps the v132 Gijon stable-runtime boundary and makes exact-date
  // visibility follow normalized occurrences without stale fail-open cards.
  const RELEASE = 133;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();