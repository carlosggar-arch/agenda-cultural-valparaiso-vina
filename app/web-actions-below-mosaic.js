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
      display: flex !important;
      grid-template-columns: none !important;
      grid-template-rows: none !important;
      flex-wrap: nowrap !important;
      align-items: stretch !important;
      justify-content: stretch !important;
      width: 100% !important;
      max-width: 100% !important;
      margin: 0 0 .14rem !important;
      padding: 0 !important;
      gap: .34rem !important;
      border: 0 !important;
      border-radius: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
      position: static !important;
      inset: auto !important;
      transform: none !important;
      overflow: hidden !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions > * {
      box-sizing: border-box !important;
      flex-basis: 0 !important;
      width: auto !important;
      max-width: none !important;
      min-width: 0 !important;
      min-height: 36px !important;
      margin: 0 !important;
      white-space: nowrap !important;
      justify-content: center !important;
      align-items: center !important;
      text-align: center !important;
      align-self: stretch !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .favorites-access--app {
      flex: 1.15 1 0 !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .header-search-toggle {
      flex: .52 1 0 !important;
      width: auto !important;
      min-width: 0 !important;
      max-width: none !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .install-button {
      flex: .9 1 0 !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .share-qr-button {
      flex: .52 1 0 !important;
      width: auto !important;
      min-width: 0 !important;
      max-width: none !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .city-switch {
      flex: 1.75 1 0 !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .contribute-source-button {
      flex: 1.25 1 0 !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .source-feedback-button {
      flex: 1.12 1 0 !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .favorites-access--app,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .install-button,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .city-switch,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .contribute-source-button,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .source-feedback-button {
      min-height: 36px !important;
      padding: .42rem .58rem !important;
      border-radius: 10px !important;
      font-size: .72rem !important;
      line-height: 1 !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .header-search-toggle,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .share-qr-button {
      display: grid !important;
      place-items: center !important;
      height: 36px !important;
      min-height: 36px !important;
      padding: 0 !important;
      border-radius: 10px !important;
    }
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .city-switch,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .contribute-source-button,
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions [data-favorites-access],
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions [data-share-qr-open],
    html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions [data-community-comments] {
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
setTimeout(syncWebActions, 1000);
window.addEventListener("resize", syncWebActions, { passive: true });
window.addEventListener("orientationchange", syncWebActions, { passive: true });
standaloneQuery?.addEventListener?.("change", syncWebActions);
desktopQuery?.addEventListener?.("change", syncWebActions);
