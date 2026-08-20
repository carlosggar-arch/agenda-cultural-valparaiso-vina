(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v162 hardens canonical source identity, single module ownership and dual-origin production smoke.
  const RELEASE = 162;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();