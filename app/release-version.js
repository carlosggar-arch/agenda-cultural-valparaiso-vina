(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v132 keeps grouped cinema sessions from v131 and makes date visibility use
  // normalized occurrences without allowing the neutral fail-open to override it.
  const RELEASE = 132;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();