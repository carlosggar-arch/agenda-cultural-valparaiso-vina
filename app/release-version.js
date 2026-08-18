(() => {
  // Single source of truth for the public PWA release and service-worker cache.
  const RELEASE = 81;
  const MIN_SAFE_SERVICE_WORKER_RELEASE = 81;
  globalThis.__VIVAMOS_RELEASE__ = RELEASE;

  // Emergency migration for browser profiles that are still controlled by one
  // of the releases that could enter a DOM mutation loop. This runs in the head,
  // before the application modules are requested, so a stale worker cannot trap
  // the user indefinitely. It is intentionally limited to pre-v81 workers; normal
  // future updates keep using the standard service-worker lifecycle.
  if (!("serviceWorker" in navigator)) return;
  const controller = navigator.serviceWorker.controller;
  if (!controller) return;

  let controllerRelease = 0;
  try {
    const controllerUrl = new URL(controller.scriptURL);
    controllerRelease = Number(controllerUrl.searchParams.get("v") || 0);
  } catch {}
  if (Number.isInteger(controllerRelease) && controllerRelease >= MIN_SAFE_SERVICE_WORKER_RELEASE) return;

  const recoveryKey = `vivamos-pwa-recovery-v${MIN_SAFE_SERVICE_WORKER_RELEASE}`;
  try {
    if (sessionStorage.getItem(recoveryKey) === "complete") return;
    sessionStorage.setItem(recoveryKey, "running");
  } catch {}

  globalThis.__VIVAMOS_RECOVERING__ = true;
  // Equivalent to pressing Stop in the browser: prevent the rest of the old app
  // bundle from starting while the stale worker/cache is being removed.
  try { window.stop(); } catch {}

  (async () => {
    try {
      const registrations = await navigator.serviceWorker.getRegistrations();
      await Promise.allSettled(registrations
        .filter((registration) => registration.scope.startsWith(new URL("./", location.href).href))
        .map((registration) => registration.unregister()));

      if ("caches" in globalThis) {
        const names = await caches.keys();
        await Promise.allSettled(names
          .filter((name) => name.startsWith("agenda-cultural-"))
          .map((name) => caches.delete(name)));
      }
    } finally {
      try { sessionStorage.setItem(recoveryKey, "complete"); } catch {}
      const url = new URL(location.href);
      url.searchParams.set("pwa_recovered", String(MIN_SAFE_SERVICE_WORKER_RELEASE));
      location.replace(url.href);
    }
  })();
})();