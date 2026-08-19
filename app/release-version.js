(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v122 shows verified museum opening hours in grouped cards across both cities
  // and gives multi-event rows enough room for complete titles, schedules and prices.
  const RELEASE = 122;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
