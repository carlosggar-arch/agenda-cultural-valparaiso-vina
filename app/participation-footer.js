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
    .header-actions {
      flex-wrap: nowrap !important;
      overflow-x: auto !important;
      overscroll-behavior-inline: contain;
      scrollbar-width: none;
    }
    .header-actions::-webkit-scrollbar { display: none; }
    .header-actions .source-feedback-button,
    .header-actions .source-like-button {
      box-sizing: border-box !important;
      flex: 0 0 auto !important;
      min-height: 42px !important;
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: .32rem !important;
      margin: 0 !important;
      padding: .58rem .72rem !important;
      border: 1px solid rgba(23,79,70,.20) !important;
      border-radius: 12px !important;
      background: rgba(255,255,255,.82) !important;
      color: var(--header-ink,#153f3a) !important;
      font: inherit !important;
      font-size: .78rem !important;
      line-height: 1 !important;
      font-weight: 780 !important;
      white-space: nowrap !important;
      box-shadow: none !important;
    }
    .header-actions .source-like-button {
      min-width: 58px !important;
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
    html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions {
      display: flex !important;
      flex-wrap: nowrap !important;
      justify-content: flex-start !important;
      align-items: stretch !important;
      width: 100% !important;
      max-width: 100% !important;
      overflow-x: auto !important;
      gap: .20rem !important;
    }
    html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions > * {
      flex: 0 0 auto !important;
      width: auto !important;
      min-width: 48px !important;
    }
    @media (max-width: 700px) {
      .header-actions .source-feedback-button,
      .header-actions .source-like-button {
        min-height: 39px !important;
        padding: .48rem .56rem !important;
        font-size: .72rem !important;
      }
    }
    @media (max-width: 430px) {
      .header-actions .source-feedback-button span { display: none; }
      .header-actions .source-feedback-button { min-width: 42px !important; }
      .header-actions .source-like-button { min-width: 50px !important; }
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
