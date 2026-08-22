import { SUPPORT_VIVAMOS, getEnabledSupportMethods } from "./support-vivamos-config.mjs";

function createSupportMenu(config = SUPPORT_VIVAMOS) {
  const methods = getEnabledSupportMethods(config);
  if (!config?.enabled || methods.length === 0) return null;

  const wrap = document.createElement("div");
  wrap.className = "vivamos-support";
  wrap.dataset.vivamosSupport = "";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "vivamos-support-toggle";
  button.textContent = config.label || "❤️ Apoya ¡Vivamos!";
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-haspopup", "menu");

  const menu = document.createElement("div");
  menu.className = "vivamos-support-menu";
  menu.hidden = true;
  menu.setAttribute("role", "menu");

  for (const method of methods) {
    const link = document.createElement("a");
    link.href = method.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute("role", "menuitem");
    link.textContent = `${method.audience} — ${method.provider}`;
    menu.append(link);
  }

  button.addEventListener("click", () => {
    const opening = menu.hidden;
    menu.hidden = !opening;
    button.setAttribute("aria-expanded", opening ? "true" : "false");
  });

  wrap.append(button, menu);
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
