(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v121 unifies equivalent venue names in grouped cards and prevents grouped
  // event rows from clipping titles, schedules or prices.
  const RELEASE = 121;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
