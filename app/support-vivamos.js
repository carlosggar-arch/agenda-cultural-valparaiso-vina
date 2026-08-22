import { SUPPORT_VIVAMOS, getEnabledSupportMethods } from "./support-vivamos-config.mjs";

function ensureSupportStyles() {
  if (document.getElementById("vivamos-support-style")) return;
  const style = document.createElement("style");
  style.id = "vivamos-support-style";
  style.textContent = `
    .vivamos-support{position:relative;display:inline-flex;align-items:center}
    .vivamos-support-toggle{display:inline-flex;align-items:center;justify-content:center;min-height:2.35rem;padding:.5rem .85rem;border:1px solid rgba(244,209,109,.65);border-radius:999px;background:transparent;color:#f4d16d;font:inherit;font-weight:850;line-height:1;white-space:nowrap;cursor:pointer;text-decoration:none}
    .vivamos-support-toggle:hover,.vivamos-support-toggle:focus-visible{background:rgba(244,209,109,.12);border-color:#f4d16d;outline:2px solid rgba(255,255,255,.65);outline-offset:2px}
    .vivamos-footer.vivamos-footer--with-support,
    .vivamos-footer.vivamos-footer--with-sources.vivamos-footer--with-support{grid-template-columns:auto minmax(0,1fr) auto auto auto auto}
    @media (max-width:900px){
      .vivamos-footer.vivamos-footer--with-support,
      .vivamos-footer.vivamos-footer--with-sources.vivamos-footer--with-support{grid-template-columns:1fr auto}
      .vivamos-support{grid-column:2}
    }
  `;
  document.head.append(style);
}

function createSupportMenu(config = SUPPORT_VIVAMOS) {
  const methods = getEnabledSupportMethods(config);
  if (!config?.enabled || methods.length === 0) return null;
  ensureSupportStyles();

  const method = methods[0];
  const wrap = document.createElement("div");
  wrap.className = "vivamos-support";
  wrap.dataset.vivamosSupport = "";

  const link = document.createElement("a");
  link.href = method.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.className = "vivamos-support-toggle";
  link.textContent = config.label || "❤️ Apoya ¡Vivamos!";
  link.setAttribute("aria-label", "Apoya ¡Vivamos! con PayPal");

  wrap.append(link);
  return wrap;
}

function mountSupport() {
  const footer = document.querySelector("body > footer");
  if (!footer) return false;

  let support = footer.querySelector("[data-vivamos-support]");
  if (!support) {
    support = createSupportMenu();
    if (!support) return false;
  }

  const sources = footer.querySelector("[data-sources-toggle], [data-sources-fallback]");
  const version = footer.querySelector("[data-app-version]");
  if (sources) {
    if (sources.nextElementSibling !== support) footer.insertBefore(support, sources.nextSibling);
  } else if (version && support.nextElementSibling !== version) {
    footer.insertBefore(support, version);
  } else if (!support.parentElement) {
    footer.append(support);
  }
  footer.classList.add("vivamos-footer--with-support");
  return true;
}

mountSupport();
window.setTimeout(mountSupport, 500);
window.setTimeout(mountSupport, 1400);
window.addEventListener("resize", mountSupport, { passive: true });
