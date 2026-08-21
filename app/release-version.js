(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v166 consolidates filter visibility and grouped-exhibition presentation into
  // single owners and retires the legacy exhibition runtimes and layout patches.
  const RELEASE = 166;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();