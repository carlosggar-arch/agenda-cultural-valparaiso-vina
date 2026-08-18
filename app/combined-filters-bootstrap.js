async function waitForBaseApp() {
  while (!globalThis.__vivamosAppBaseReady) {
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
  await globalThis.__vivamosAppBaseReady;
}

await waitForBaseApp();
await import("./category-normalizer.js?v=20260818-categories3");
await import("./combined-filters.js?v=20260818-public-taxonomy1");
await import("./approved-event-integrity.js?v=20260818-integrity1");
