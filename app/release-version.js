(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v209 refreshes the Maps module so installed Apps receive the 25 px control.
  const RELEASE = 209;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
