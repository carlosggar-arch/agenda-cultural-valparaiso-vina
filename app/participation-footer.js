const footer = document.querySelector("body > footer");

function mountParticipationRail() {
  if (!footer) return false;

  const sourceCta = document.querySelector("[data-source-proposal-cta]");
  const sourceActions = sourceCta?.querySelector(".source-proposal-actions");
  const contact = footer.querySelector(".vivamos-footer-contact");
  if (!sourceActions || !contact) return false;

  let rail = footer.querySelector("[data-vivamos-participation-rail]");
  if (!rail) {
    rail = document.createElement("div");
    rail.className = "vivamos-participation-rail";
    rail.dataset.vivamosParticipationRail = "";
    rail.setAttribute("aria-label", "Participa y contacta con ¡Vivamos!");
    footer.insertBefore(rail, footer.querySelector("[data-app-version]") || null);
  }

  if (contact.parentElement !== rail) rail.append(contact);
  while (sourceActions.firstChild) rail.append(sourceActions.firstChild);

  // Keep the original marker in the hidden Sources section so community-source.js
  // does not create a duplicate CTA after a city change.
  sourceCta.hidden = true;
  sourceCta.setAttribute("aria-hidden", "true");

  // The user explicitly asked to remove the old standalone Sources footer button.
  footer.querySelector("[data-sources-toggle]")?.remove();
  return true;
}

function retryMount(attempt = 0) {
  if (mountParticipationRail() || attempt >= 20) return;
  window.setTimeout(() => retryMount(attempt + 1), 100);
}

retryMount();

// sources-toggle.js can finish after this module on a slow connection; remove its
// legacy footer button once more without observing the event grid or scroll.
window.setTimeout(() => {
  footer?.querySelector("[data-sources-toggle]")?.remove();
  mountParticipationRail();
}, 1200);

const STYLE_ID = "vivamos-participation-footer-style";
if (!document.getElementById(STYLE_ID)) {
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .vivamos-participation-rail {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: nowrap;
      gap: .45rem;
      min-width: 0;
      white-space: nowrap;
      overflow-x: auto;
      overscroll-behavior-inline: contain;
      scrollbar-width: none;
    }
    .vivamos-participation-rail::-webkit-scrollbar { display: none; }
    .vivamos-participation-rail .vivamos-footer-contact,
    .vivamos-participation-rail .source-proposal-link,
    .vivamos-participation-rail .source-feedback-button,
    .vivamos-participation-rail .source-like-button {
      flex: 0 0 auto;
      min-height: 2.35rem;
      margin: 0;
      padding: .5rem .8rem;
      border-radius: 999px;
      font-size: .82rem;
      line-height: 1;
    }
    .vivamos-participation-rail .source-proposal-link {
      border-color: rgba(255,255,255,.62);
      background: transparent;
      color: #fff;
    }
    .vivamos-participation-rail .source-feedback-button,
    .vivamos-participation-rail .source-like-button {
      border-color: rgba(255,255,255,.42);
      background: rgba(255,255,255,.08);
      color: #fff;
    }
    .vivamos-participation-rail .source-like-button[data-liked="true"] {
      border-color: #f2b8af;
      background: rgba(255,244,242,.15);
      color: #ffd7d0;
    }
    [data-source-proposal-cta][hidden] { display: none !important; }

    @media (max-width: 900px) {
      .vivamos-footer .vivamos-footer-identity {
        grid-column: 1;
        grid-row: 1;
      }
      .vivamos-footer .vivamos-footer-credit {
        grid-column: 1;
        grid-row: 2;
      }
      .vivamos-footer .vivamos-participation-rail {
        grid-column: 2;
        grid-row: 1 / span 2;
        align-self: center;
        justify-content: flex-start;
        max-width: min(52vw, 430px);
        padding-bottom: .1rem;
      }
      .vivamos-footer .vivamos-participation-rail .vivamos-footer-contact {
        width: auto;
      }
      .vivamos-footer [data-app-version] {
        display: none;
      }
    }
    @media (max-width: 560px) {
      .vivamos-footer {
        grid-template-columns: auto minmax(0,1fr) !important;
        align-items: center !important;
        gap: .45rem .65rem !important;
      }
      .vivamos-footer .vivamos-footer-identity {
        grid-column: 1;
        grid-row: 1;
        display: block;
        white-space: nowrap;
      }
      .vivamos-footer .vivamos-footer-identity span,
      .vivamos-footer .vivamos-footer-credit {
        display: none;
      }
      .vivamos-footer .vivamos-participation-rail {
        grid-column: 2;
        grid-row: 1;
        max-width: calc(100vw - 7rem);
        min-width: 0;
      }
      .vivamos-participation-rail .vivamos-footer-contact,
      .vivamos-participation-rail .source-proposal-link,
      .vivamos-participation-rail .source-feedback-button,
      .vivamos-participation-rail .source-like-button {
        min-height: 2.2rem;
        padding: .48rem .62rem;
        font-size: .77rem;
      }
      .vivamos-participation-rail .source-action-long { display: none; }
      .vivamos-participation-rail .source-action-short { display: inline; }
      .vivamos-participation-rail .source-feedback-button span { display: none; }
    }
  `;
  document.head.append(style);
}
