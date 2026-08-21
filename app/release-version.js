(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v169 keeps the visible footer release label aligned after footer reconstruction.
  const RELEASE = 169;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
