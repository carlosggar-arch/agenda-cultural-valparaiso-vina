(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v173 canonicalizes exhibition venues before grouping and presentation.
  const RELEASE = 173;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
