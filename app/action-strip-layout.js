const STYLE_ID = "vivamos-action-strip-fill";

function installActionStripLayout() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Wide layouts: use the full strip without making every control equally wide.
       Short/icon controls get a smaller share; text-heavy controls get more. */
    @media (min-width: 701px) {
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions {
        display: flex !important;
        flex-wrap: nowrap !important;
        align-items: stretch !important;
        justify-content: stretch !important;
        width: 100% !important;
        max-width: 100% !important;
        gap: .34rem !important;
        overflow: hidden !important;
      }

      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions > *,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions > * {
        box-sizing: border-box !important;
        flex-basis: 0 !important;
        width: auto !important;
        max-width: none !important;
        min-width: 0 !important;
        align-self: stretch !important;
      }

      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .favorites-access--app,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .favorites-access--app {
        flex: 1.15 1 0 !important;
      }
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .header-search-toggle,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .header-search-toggle {
        flex: .52 1 0 !important;
        width: auto !important;
        max-width: none !important;
      }
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .install-button,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .install-button {
        flex: .9 1 0 !important;
      }
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .share-qr-button,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .share-qr-button {
        flex: .52 1 0 !important;
        width: auto !important;
        max-width: none !important;
      }
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .city-switch,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .city-switch {
        flex: 1.75 1 0 !important;
      }
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .contribute-source-button,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .contribute-source-button {
        flex: 1.25 1 0 !important;
      }
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .source-feedback-button,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .source-feedback-button {
        flex: 1.12 1 0 !important;
      }
      html[data-web-actions-below-mosaic="true"] .filter-workbench > .header-actions .source-like-button,
      html[data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions .source-like-button {
        flex: .62 1 0 !important;
        width: auto !important;
        min-width: 0 !important;
        max-width: none !important;
      }
    }
  `;
  document.head.append(style);
}

installActionStripLayout();
