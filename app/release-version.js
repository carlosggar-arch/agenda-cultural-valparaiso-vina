(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v178 fixes visible-date venue hours and grouped exhibition hours in Gijón.
  const RELEASE = 178;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();