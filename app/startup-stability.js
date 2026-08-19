const STYLE_ID = "vivamos-startup-stability";
const SAFE_MODE_DELAY_MS = 5000;

function installStartupStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    html:not([data-vivamos-ready="true"]) main > .discovery,
    html:not([data-vivamos-ready="true"]) main > .agenda {
      visibility: hidden !important;
    }
  `;
  document.head.append(style);
}

function ready() {
  return document.documentElement.dataset.vivamosReady === "true";
}

function showFallbackFailure(error) {
  document.documentElement.dataset.vivamosReady = "true";
  document.documentElement.dataset.vivamosSafeMode = "failed";
  const status = document.querySelector("[data-status]");
  if (!status) return;
  status.hidden = false;
  status.innerHTML = '<strong>No pudimos iniciar la agenda</strong><p>Recarga la página. Si el problema continúa, la aplicación conserva el diagnóstico para poder corregirlo.</p>';
  console.error("¡Vivamos!: el modo seguro tampoco pudo iniciar", error);
}

async function startSafeMode() {
  if (ready()) return;
  document.documentElement.dataset.vivamosSafeMode = "starting";
  try {
    const module = await import("./app-safe-mode.js?v=20260819-safe1");
    if (!ready()) await module.startSafeMode();
  } catch (error) {
    if (!ready()) showFallbackFailure(error);
  }
}

installStartupStyle();
const watchdog = window.setTimeout(startSafeMode, SAFE_MODE_DELAY_MS);
window.addEventListener("vivamos:core-ready", () => window.clearTimeout(watchdog), { once: true });
