const desktopQuery = window.matchMedia?.("(min-width: 701px)");
const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");

function isDesktopWeb() {
  const standalone = Boolean(standaloneQuery?.matches || window.navigator.standalone === true);
  return !standalone && Boolean(desktopQuery?.matches || Number(window.innerWidth || 0) > 700);
}

function ensureStyles() {
  let style = document.querySelector("[data-web-actions-below-mosaic-style]");
  if (style) return style;
  style = document.createElement("style");
  style.dataset.webActionsBelowMosaicStyle = "true";
  style.textContent = `
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions {
      grid-column: 1 / -1 !important;
      display: grid !important;
      grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)) !important;
      align-items: stretch !important;
      width: 100% !important;
      max-width: none !important;
      margin: 0 0 .42rem !important;
      padding: .34rem .38rem !important;
      gap: .34rem !important;
      border: 1px solid rgba(23,79,70,.18) !important;
      border-radius: 14px !important;
      background: rgba(255,255,255,.78) !important;
      box-shadow: none !important;
      position: static !important;
      inset: auto !important;
      transform: none !important;
      overflow: visible !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions > * {
      box-sizing: border-box !important;
      width: 100% !important;
      min-width: 0 !important;
      min-height: 46px !important;
      margin: 0 !important;
      justify-content: center !important;
      align-items: center !important;
      text-align: center !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .header-search-toggle {
      display: grid !important;
      place-items: center !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .city-switch,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .contribute-source-button,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions [data-favorites-access],
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions [data-share-qr-open] {
      display: flex !important;
      visibility: visible !important;
      opacity: 1 !important;
    }
    html[data-web-actions-below-mosaic="true"] .header-bottom {
      display: none !important;
    }
  `;
  document.head.append(style);
  return style;
}

function syncWebActions() {
  const actions = document.querySelector(".header-actions");
  const workbench = document.querySelector(".filter-workbench");
  const header = document.querySelector(".app-header");
  const bottom = document.querySelector(".header-bottom");
  if (!actions || !workbench || !header) return;

  if (isDesktopWeb()) {
    ensureStyles();
    document.documentElement.dataset.webActionsBelowMosaic = "true";
    if (actions.parentElement !== workbench || actions !== workbench.firstElementChild) {
      workbench.insertBefore(actions, workbench.firstElementChild);
    }
    if (bottom) bottom.hidden = true;
    return;
  }

  delete document.documentElement.dataset.webActionsBelowMosaic;
}

syncWebActions();
requestAnimationFrame(syncWebActions);
setTimeout(syncWebActions, 250);
window.addEventListener("resize", syncWebActions);
window.addEventListener("orientationchange", syncWebActions);
standaloneQuery?.addEventListener?.("change", syncWebActions);
desktopQuery?.addEventListener?.("change", syncWebActions);

new MutationObserver(() => queueMicrotask(syncWebActions)).observe(document.body, { childList: true, subtree: true });
