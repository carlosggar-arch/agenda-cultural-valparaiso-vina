(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v181 loads date-specific exhibition venue hours in the shared runtime, including Gijón.
  const RELEASE = 181;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();