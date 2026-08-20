(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v159 hardens Cloudflare/GitHub image fallback parity for transient image failures.
  const RELEASE = 159;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
