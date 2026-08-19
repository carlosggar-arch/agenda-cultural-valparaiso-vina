(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v135 keeps the normalized date pipeline and makes Gijon grouped exhibitions
  // filter-aware, merges Museos into Exposiciones and restores light card images.
  const RELEASE = 135;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
