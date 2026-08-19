(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v118 removes the extra temporal-priority presentation while preserving the
  // conservative date-confidence guard used by the existing time filters.
  const RELEASE = 118;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
