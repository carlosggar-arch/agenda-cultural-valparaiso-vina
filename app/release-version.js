(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  // v205 sets the Maps affordance to a 25 px square with an 18 px arrow icon.
  const RELEASE = 205;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;
})();
