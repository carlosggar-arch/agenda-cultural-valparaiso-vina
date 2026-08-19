const STYLE_ID = "vivamos-installed-six-actions";

function installSixActionStrip() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    /* Installed mobile PWA: the public like control is retired, so the six
       remaining actions must fill the strip without leaving an empty slot. */
    html[data-installed-real-mosaic="true"][data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions {
      grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
    }

    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-community-like],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > .source-like-button {
      display: none !important;
      visibility: hidden !important;
      width: 0 !important;
      min-width: 0 !important;
      max-width: 0 !important;
      padding: 0 !important;
      margin: 0 !important;
      border: 0 !important;
    }
  `;
  document.head.append(style);
}

installSixActionStrip();
