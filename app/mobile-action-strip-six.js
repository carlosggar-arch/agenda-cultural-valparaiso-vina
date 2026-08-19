const STYLE_ID = "vivamos-installed-six-actions";

function installSixActionStrip() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    html[data-installed-real-mosaic="true"][data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions {
      display: grid !important;
      grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
      grid-template-rows: 38px !important;
      width: 100% !important;
      max-width: 100% !important;
      gap: 0 !important;
      overflow: hidden !important;
    }
    html[data-installed-real-mosaic="true"][data-installed-app-actions="below-mosaic"] body .filter-workbench > .header-actions > * {
      box-sizing: border-box !important;
      width: 100% !important;
      min-width: 0 !important;
      max-width: none !important;
      height: 38px !important;
      min-height: 38px !important;
      margin: 0 !important;
      border-radius: 0 !important;
      justify-self: stretch !important;
      align-self: stretch !important;
    }
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-community-like],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > .source-like-button {
      display: none !important;
    }
  `;
  document.head.append(style);
}

installSixActionStrip();
