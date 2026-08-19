(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v125 fixes the program-reference observer feedback loop that could starve
  // startup before the selected city's dataset finished loading.
  const RELEASE = 125;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();