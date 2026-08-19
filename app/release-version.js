(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v120 makes the temporal confidence guard non-blocking and keeps exhibitions
  // at the end of the unfiltered dated agenda.
  const RELEASE = 120;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
