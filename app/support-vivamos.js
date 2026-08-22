import { SUPPORT_VIVAMOS, getEnabledSupportMethods } from "./support-vivamos-config.mjs";

function ensureSupportStyles() {
  if (document.getElementById("vivamos-support-style")) return;
  const style = document.createElement("style");
  style.id = "vivamos-support-style";
  style.textContent = `
    .vivamos-support{position:relative;display:inline-flex;align-items:center}
    .vivamos-support-toggle{display:inline-flex;align-items:center;justify-content:center;min-height:2.35rem;padding:.5rem .85rem;border:1px solid rgba(244,209,109,.65);border-radius:999px;background:transparent;color:#f4d16d;font:inherit;font-weight:850;line-height:1;white-space:nowrap;cursor:pointer}
    .vivamos-support-toggle:hover,.vivamos-support-toggle:focus-visible{background:rgba(244,209,109,.12);border-color:#f4d16d;outline:2px solid rgba(255,255,255,.65);outline-offset:2px}
    .vivamos-support-menu{position:absolute;z-index:30;right:0;bottom:calc(100% + .55rem);min-width:230px;padding:.4rem;border:1px solid rgba(23,79,70,.16);border-radius:14px;background:#fff;box-shadow:0 14px 36px rgba(6,35,31,.24)}
    .vivamos-support-menu[hidden]{display:none!important}
    .vivamos-support-menu a{display:block;padding:.7rem .8rem;border-radius:10px;color:#174f46;text-decoration:none;font-weight:780;white-space:nowrap}
    .vivamos-support-menu a:hover,.vivamos-support-menu a:focus-visible{background:#f7f3e5;outline:none}
    .vivamos-footer.vivamos-footer--with-support,
    .vivamos-footer.vivamos-footer--with-sources.vivamos-footer--with-support{grid-template-columns:auto minmax(0,1fr) auto auto auto auto}
    @media (max-width:900px){
      .vivamos-footer.vivamos-footer--with-support,
      .vivamos-footer.vivamos-footer--with-sources.vivamos-footer--with-support{grid-template-columns:1fr auto}
      .vivamos-support{grid-column:2}
      .vivamos-support-menu{right:0;max-width:min(280px,calc(100vw - 2rem))}
    }
  `;
  document.head.append(style);
}

function createSupportMenu(config = SUPPORT_VIVAMOS) {
  const methods = getEnabledSupportMethods(config);
  if (!config?.enabled || methods.length === 0) return null;
  ensureSupportStyles();

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

  const closeMenu = () => {
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
  };
  button.addEventListener("click", () => {
    const opening = menu.hidden;
    menu.hidden = !opening;
    button.setAttribute("aria-expanded", opening ? "true" : "false");
  });
  document.addEventListener("click", (event) => {
    if (!wrap.contains(event.target)) closeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });

  wrap.append(button, menu);
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
