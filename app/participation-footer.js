const footer = document.querySelector("body > footer");
const SUPPORT_PAYPAL_URL = "https://www.paypal.com/ncp/payment/MMR5A78JMY5VL";
const SUPPORT_LABEL = "❤️ Apoya ¡Vivamos!";

function restoreFooterContact() {
  if (!footer) return;
  const rail = footer.querySelector("[data-vivamos-participation-rail]");
  const contact = rail?.querySelector(".vivamos-footer-contact");
  const version = footer.querySelector("[data-app-version]");
  if (contact) footer.insertBefore(contact, version || null);
  rail?.remove();

  // Fuentes is owned by app.js/sources-toggle.js. This module may run again
  // after those modules (retry timer, delayed mount or resize), so it must
  // preserve whichever source access is already installed instead of deleting it.
  const sourcesAccess = footer.querySelector("[data-sources-toggle], [data-sources-fallback]");
  const supportAccess = footer.querySelector("[data-vivamos-support]");
  if (sourcesAccess && supportAccess && sourcesAccess.nextElementSibling !== supportAccess) {
    footer.insertBefore(sourcesAccess, supportAccess);
  } else if (sourcesAccess && !supportAccess && version && sourcesAccess.nextElementSibling !== version) {
    footer.insertBefore(sourcesAccess, version);
  }
}

function ensureSupportStyles() {
  const STYLE_ID = "vivamos-support-style";
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .vivamos-support {
      position: relative;
      display: inline-flex;
      align-items: center;
    }
    .vivamos-support-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 2.35rem;
      padding: .5rem .85rem;
      border: 1px solid rgba(244,209,109,.65);
      border-radius: 999px;
      background: transparent;
      color: #f4d16d;
      font: inherit;
      font-weight: 850;
      line-height: 1;
      white-space: nowrap;
      cursor: pointer;
      text-decoration: none;
    }
    .vivamos-support-toggle:hover,
    .vivamos-support-toggle:focus-visible {
      background: rgba(244,209,109,.12);
      border-color: #f4d16d;
      outline: 2px solid rgba(255,255,255,.65);
      outline-offset: 2px;
    }
    .vivamos-footer.vivamos-footer--with-support,
    .vivamos-footer.vivamos-footer--with-sources.vivamos-footer--with-support {
      grid-template-columns: auto minmax(0,1fr) auto auto auto auto;
    }
    @media (max-width: 900px) {
      .vivamos-footer.vivamos-footer--with-support,
      .vivamos-footer.vivamos-footer--with-sources.vivamos-footer--with-support {
        grid-template-columns: 1fr auto;
      }
      .vivamos-support { grid-column: 2; }
    }
  `;
  document.head.append(style);
}

function mountSupport() {
  if (!footer) return false;
  ensureSupportStyles();

  let support = footer.querySelector("[data-vivamos-support]");
  if (!support) {
    support = document.createElement("div");
    support.className = "vivamos-support";
    support.dataset.vivamosSupport = "";

    const link = document.createElement("a");
    link.href = SUPPORT_PAYPAL_URL;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "vivamos-support-toggle";
    link.textContent = SUPPORT_LABEL;
    link.setAttribute("aria-label", "Apoya ¡Vivamos! con PayPal");
    support.append(link);
  }

  const sources = footer.querySelector("[data-sources-toggle], [data-sources-fallback]");
  const version = footer.querySelector("[data-app-version]");
  if (sources) {
    if (sources.nextElementSibling !== support) footer.insertBefore(support, sources.nextSibling);
  } else if (version) {
    if (support.nextElementSibling !== version) footer.insertBefore(support, version);
  } else if (!support.parentElement) {
    footer.append(support);
  }
  footer.classList.add("vivamos-footer--with-support");
  return true;
}

function ensureHeaderFeedbackStyles() {
  const STYLE_ID = "vivamos-header-feedback-style";
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .header-actions .source-feedback-button {
      display: inline-flex !important;
      align-items: center !important;
      justify-content: center !important;
      gap: .28rem !important;
      min-height: 36px !important;
      padding: .42rem .58rem !important;
      border: 1px solid rgba(23,79,70,.20) !important;
      border-radius: 10px !important;
      background: rgba(255,255,255,.82) !important;
      color: var(--header-ink,#153f3a) !important;
      font: inherit !important;
      font-size: .72rem !important;
      line-height: 1 !important;
      font-weight: 780 !important;
      white-space: nowrap !important;
      box-shadow: none !important;
    }

    /* Installed mobile app: exactly six public actions, filling the whole row. */
    html[data-installed-real-mosaic="true"][data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions {
      display: grid !important;
      grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
      grid-template-rows: 38px !important;
      width: 100% !important;
      max-width: 100% !important;
      gap: 0 !important;
      padding: 0 !important;
      margin: 0 !important;
      overflow: hidden !important;
      border-radius: 9px !important;
    }
    html[data-installed-real-mosaic="true"][data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions > * {
      box-sizing: border-box !important;
      width: 100% !important;
      min-width: 0 !important;
      max-width: none !important;
      height: 38px !important;
      min-height: 38px !important;
      margin: 0 !important;
      padding: .12rem .08rem !important;
      border-radius: 0 !important;
      overflow: hidden !important;
      justify-self: stretch !important;
      align-self: stretch !important;
    }
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-community-like],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > .source-like-button {
      display: none !important;
    }

    @media (max-width: 430px) {
      .header-actions .source-feedback-button span { display: none; }
    }
  `;
  document.head.append(style);
}

function mountHeaderFeedback() {
  restoreFooterContact();
  mountSupport();
  const actions = document.querySelector(".header-actions");
  const contribute = actions?.querySelector("[data-contribute-source]");
  const sourceCta = document.querySelector("[data-source-proposal-cta]");
  const sourceActions = sourceCta?.querySelector(".source-proposal-actions");
  const comments = sourceActions?.querySelector("[data-community-comments]") || document.querySelector("[data-community-comments]");
  if (!actions || !contribute || !comments) return false;

  ensureHeaderFeedbackStyles();
  if (comments.parentElement !== actions) contribute.insertAdjacentElement("afterend", comments);
  actions.querySelectorAll("[data-community-like], .source-like-button").forEach((node) => node.remove());

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

mountSupport();
retryMount();
window.setTimeout(mountSupport, 500);
window.setTimeout(mountHeaderFeedback, 1200);
window.setTimeout(mountSupport, 1400);
window.addEventListener("resize", () => {
  mountHeaderFeedback();
  mountSupport();
}, { passive: true });
