import { SUPPORT_VIVAMOS, getEnabledSupportMethods } from "./support-vivamos-config.mjs";

function createSupportMenu(config = SUPPORT_VIVAMOS) {
  const methods = getEnabledSupportMethods(config);
  if (!config?.enabled || methods.length === 0) return null;

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
  if (!footer || footer.querySelector("[data-vivamos-support]")) return false;

  const support = createSupportMenu();
  if (!support) return false;

  const sources = footer.querySelector("[data-sources-toggle], [data-sources-fallback]");
  if (sources?.nextSibling) footer.insertBefore(support, sources.nextSibling);
  else if (sources) footer.append(support);
  else footer.append(support);
  return true;
}

export { createSupportMenu, mountSupport };

mountSupport();
