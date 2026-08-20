(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v164 separates enrollment/booking processes from dated cultural events in a shared multi-city reminder section.
  const RELEASE = 164;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();