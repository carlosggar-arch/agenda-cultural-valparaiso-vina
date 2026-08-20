(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v164 binds datasets/diagnostics to one release generation, centralizes venue facts and aliases, and generates the PWA shell manifest.
  const RELEASE = 164;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
