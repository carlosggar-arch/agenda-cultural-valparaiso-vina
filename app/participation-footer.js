const footer = document.querySelector("body > footer");

function restoreFooterContact() {
  if (!footer) return;
  const rail = footer.querySelector("[data-vivamos-participation-rail]");
  const contact = rail?.querySelector(".vivamos-footer-contact");
  const version = footer.querySelector("[data-app-version]");
  if (contact) footer.insertBefore(contact, version || null);
  rail?.remove();
  footer.querySelector("[data-sources-toggle]")?.remove();
}

function ensureHeaderFeedbackStyles() {
  const STYLE_ID = "vivamos-header-feedback-style";
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Keep the complete action bar compact in WEB and PWA.  Several older
       responsive layers used grid/stretch rules; these selectors deliberately
       have higher specificity so no action can grow to a full row. */
    .app-header .header-actions,
    .filter-workbench > .header-actions {
      display: flex !important;
      grid-template-columns: none !important;
      grid-template-rows: none !important;
      align-items: center !important;
      justify-content: flex-start !important;
      flex-wrap: nowrap !important;
      width: auto !important;
      max-width: 100% !important;
      gap: .34rem !important;
      overflow-x: auto !important;
      overflow-y: hidden !important;
      overscroll-behavior-inline: contain;
      scrollbar-width: none;
    }
    .header-actions::-webkit-scrollbar { display: none; }

    .app-header .header-actions > *,
    .filter-workbench > .header-actions > * {
      box-sizing: border-box !important;
      flex: 0 0 auto !important;
      width: max-content !important;
      max-width: max-content !important;
      min-width: 0 !important;
      min-height: 36px !important;
      margin: 0 !important;
      white-space: nowrap !important;
      justify-self: start !important;
      align-self: center !important;
    }

    .app-header .header-actions .favorites-access--app,
    .app-header .header-actions .install-button,
    .app-header .header-actions .city-switch,
    .app-header .header-actions .contribute-source-button,
    .app-header .header-actions .source-feedback-button,
    .filter-workbench > .header-actions .favorites-access--app,
    .filter-workbench > .header-actions .install-button,
    .filter-workbench > .header-actions .city-switch,
    .filter-workbench > .header-actions .contribute-source-button,
    .filter-workbench > .header-actions .source-feedback-button {
      min-height: 36px !important;
      padding: .42rem .58rem !important;
      border-radius: 10px !important;
      font-size: .72rem !important;
      line-height: 1 !important;
    }

    .app-header .header-actions .header-search-toggle,
    .app-header .header-actions .share-qr-button,
    .filter-workbench > .header-actions .header-search-toggle,
    .filter-workbench > .header-actions .share-qr-button {
      width: 36px !important;
      min-width: 36px !important;
      max-width: 36px !important;
      min-height: 36px !important;
      height: 36px !important;
      padding: 0 !important;
      border-radius: 10px !important;
    }

    .app-header .header-actions .source-feedback-button,
    .app-header .header-actions .source-like-button,
    .filter-workbench > .header-actions .source-feedback-button,
    .filter-workbench > .header-actions .source-like-button {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: .28rem !important;
      border: 1px solid rgba(23,79,70,.20) !important;
      background: rgba(255,255,255,.82) !important;
      color: var(--header-ink,#153f3a) !important;
      font: inherit !important;
      font-size: .72rem !important;
      line-height: 1 !important;
      font-weight: 780 !important;
      box-shadow: none !important;
    }
    .app-header .header-actions .source-like-button,
    .filter-workbench > .header-actions .source-like-button {
      width: max-content !important;
      min-width: 48px !important;
      max-width: 64px !important;
      min-height: 36px !important;
      padding: .42rem .52rem !important;
      border-radius: 10px !important;
      font-variant-numeric: tabular-nums;
    }
    .header-actions .source-like-button[data-liked="true"] {
      border-color: #e0a19a !important;
      background: #fff4f2 !important;
      color: #9f3c33 !important;
    }
    .header-actions .source-like-button[data-like-pending="true"] {
      outline: 2px dotted rgba(159,60,51,.35);
      outline-offset: -4px;
    }

    /* Installed mode previously stretched every action to 100% in a grid.
       Override that exact contract with a compact, horizontally scrollable rail. */
    html[data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions {
      display: flex !important;
      grid-template-columns: none !important;
      grid-template-rows: none !important;
      align-items: center !important;
      justify-content: flex-start !important;
      flex-wrap: nowrap !important;
      width: 100% !important;
      max-width: 100% !important;
      margin: 0 0 .08rem !important;
      padding: 0 !important;
      gap: .28rem !important;
      overflow-x: auto !important;
      overflow-y: hidden !important;
    }
    html[data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions > * {
      flex: 0 0 auto !important;
      width: max-content !important;
      max-width: max-content !important;
      min-width: 0 !important;
      min-height: 36px !important;
      padding: .42rem .54rem !important;
      border-radius: 10px !important;
      font-size: .70rem !important;
      line-height: 1 !important;
      white-space: nowrap !important;
      text-align: center !important;
      justify-self: start !important;
      align-self: center !important;
    }
    html[data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions .header-search-toggle,
    html[data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions .share-qr-button {
      width: 36px !important;
      min-width: 36px !important;
      max-width: 36px !important;
      height: 36px !important;
      padding: 0 !important;
    }
    html[data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions .source-like-button {
      width: max-content !important;
      min-width: 48px !important;
      max-width: 64px !important;
      padding: .42rem .50rem !important;
    }

    @media (max-width: 700px) {
      .app-header .header-actions,
      .filter-workbench > .header-actions {
        gap: .28rem !important;
      }
      .app-header .header-actions > *,
      .filter-workbench > .header-actions > * {
        min-height: 34px !important;
      }
      .app-header .header-actions .favorites-access--app,
      .app-header .header-actions .install-button,
      .app-header .header-actions .city-switch,
      .app-header .header-actions .contribute-source-button,
      .app-header .header-actions .source-feedback-button,
      .filter-workbench > .header-actions .favorites-access--app,
      .filter-workbench > .header-actions .install-button,
      .filter-workbench > .header-actions .city-switch,
      .filter-workbench > .header-actions .contribute-source-button,
      .filter-workbench > .header-actions .source-feedback-button {
        min-height: 34px !important;
        padding: .38rem .50rem !important;
        font-size: .68rem !important;
      }
      .app-header .header-actions .header-search-toggle,
      .app-header .header-actions .share-qr-button,
      .filter-workbench > .header-actions .header-search-toggle,
      .filter-workbench > .header-actions .share-qr-button {
        width: 34px !important;
        min-width: 34px !important;
        max-width: 34px !important;
        height: 34px !important;
        min-height: 34px !important;
      }
      .app-header .header-actions .source-like-button,
      .filter-workbench > .header-actions .source-like-button {
        min-width: 46px !important;
        min-height: 34px !important;
        padding: .38rem .46rem !important;
        font-size: .68rem !important;
      }
    }
    @media (max-width: 430px) {
      .header-actions .source-feedback-button span { display: none; }
      .app-header .header-actions .source-feedback-button,
      .filter-workbench > .header-actions .source-feedback-button { min-width: 34px !important; }
    }
  `;
  document.head.append(style);
}

function mountHeaderFeedback() {
  restoreFooterContact();
  const actions = document.querySelector(".header-actions");
  const contribute = actions?.querySelector("[data-contribute-source]");
  const sourceCta = document.querySelector("[data-source-proposal-cta]");
  const sourceActions = sourceCta?.querySelector(".source-proposal-actions");
  const comments = sourceActions?.querySelector("[data-community-comments]") || document.querySelector("[data-community-comments]");
  const like = sourceActions?.querySelector("[data-community-like]") || document.querySelector("[data-community-like]");
  if (!actions || !contribute || !comments || !like) return false;

  ensureHeaderFeedbackStyles();
  if (comments.parentElement !== actions) contribute.insertAdjacentElement("afterend", comments);
  if (like.parentElement !== actions) comments.insertAdjacentElement("afterend", like);

  if (sourceCta) {
    sourceCta.hidden = true;
    sourceCta.setAttribute("aria-hidden", "true");
  }
  return true;
}

function retryMount(attempt = 0) {
  if (mountHeaderFeedback() || attempt >= 30) return;
  window.setTimeout(() => retryMount(attempt + 1), 100);
}

retryMount();
window.setTimeout(mountHeaderFeedback, 1200);
window.addEventListener("resize", mountHeaderFeedback, { passive: true });
