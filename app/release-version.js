(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v176 shows only the exhibition hours that apply to the date being viewed.
  const RELEASE = 176;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
