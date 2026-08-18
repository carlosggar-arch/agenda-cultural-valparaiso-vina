const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const mobileQuery = window.matchMedia?.("(max-width: 700px)");

function isInstalledMobile() {
  const standalone = Boolean(standaloneQuery?.matches || window.navigator.standalone === true);
  const mobile = Boolean(mobileQuery?.matches || Number(window.innerWidth || 9999) <= 700);
  return standalone && mobile;
}

function ensureMosaicOverrideStyle() {
  let style = document.querySelector("[data-installed-real-mosaic-style]");
  if (style) return style;
  style = document.createElement("style");
  style.dataset.installedRealMosaicStyle = "true";
  style.textContent = `
    html[data-installed-real-mosaic="true"] .filter-workbench::before {
      content: none !important;
      display: none !important;
    }
    html[data-installed-real-mosaic="true"][data-installed-app-actions="below-mosaic"] .filter-workbench > .header-actions {
      display: grid !important;
      grid-template-columns: repeat(5, minmax(0, 1fr)) !important;
      width: 100% !important;
      gap: .20rem !important;
      visibility: visible !important;
      opacity: 1 !important;
    }
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-favorites-access],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-header-search-toggle],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-share-qr-open],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-city-switch],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-contribute-source] {
      visibility: visible !important;
      opacity: 1 !important;
    }
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-favorites-access],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-city-switch],
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-contribute-source] {
      display: flex !important;
    }
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-header-search-toggle] {
      display: grid !important;
    }
    html[data-installed-real-mosaic="true"] .filter-workbench > .header-actions > [data-share-qr-open] {
      display: inline-flex !important;
    }
  `;
  document.head.append(style);
  return style;
}

function paintDivider(divider) {
  divider.style.setProperty("display", "block", "important");
  divider.style.setProperty("position", "relative", "important");
  divider.style.setProperty("z-index", "20", "important");
  divider.style.setProperty("box-sizing", "border-box", "important");
  divider.style.setProperty("height", "12px", "important");
  divider.style.setProperty("min-height", "12px", "important");
  divider.style.setProperty("max-height", "12px", "important");
  divider.style.setProperty("border-radius", "5px", "important");
  divider.style.setProperty("background-color", "#0b7f93", "important");
  divider.style.setProperty("background-image", 'url("../assets/mosaic-top.png")', "important");
  divider.style.setProperty("background-position", "center", "important");
  divider.style.setProperty("background-size", "22rem 100%", "important");
  divider.style.setProperty("background-repeat", "repeat-x", "important");
  divider.style.setProperty("box-shadow", "inset 0 0 0 1px rgb(255 255 255 / 28%)", "important");
  divider.style.setProperty("visibility", "visible", "important");
  divider.style.setProperty("opacity", "1", "important");
  divider.style.setProperty("pointer-events", "none", "important");
}

function styleInstalledDivider(divider, margin) {
  paintDivider(divider);
  divider.style.setProperty("width", "calc(100vw - 2rem)", "important");
  divider.style.setProperty("max-width", "none", "important");
  divider.style.setProperty("left", "50%", "important");
  divider.style.setProperty("transform", "translateX(-50%)", "important");
  divider.style.setProperty("margin", margin, "important");
}

function styleWebContentDivider(divider, workbench) {
  paintDivider(divider);
  const width = Math.max(0, Math.round(workbench.getBoundingClientRect().width));
  divider.style.setProperty("width", width ? `${width}px` : "100%", "important");
  divider.style.setProperty("max-width", "100%", "important");
  divider.style.setProperty("left", "auto", "important");
  divider.style.setProperty("transform", "none", "important");
  divider.style.setProperty("margin", ".35rem auto .42rem", "important");
}

function syncMosaics() {
  let topDivider = document.querySelector("[data-installed-mosaic-divider]");
  let contentDivider = document.querySelector("[data-installed-mosaic-divider-content]");
  const installed = isInstalledMobile();
  const header = document.querySelector(".app-header");
  const workbench = document.querySelector(".filter-workbench");
  if (!workbench) return;

  if (installed) {
    if (!header) return;
    ensureMosaicOverrideStyle();
    document.documentElement.dataset.installedRealMosaic = "true";

    if (!topDivider) {
      topDivider = document.createElement("div");
      topDivider.dataset.installedMosaicDivider = "true";
      topDivider.setAttribute("aria-hidden", "true");
      header.insertAdjacentElement("afterend", topDivider);
    } else if (topDivider.previousElementSibling !== header) {
      header.insertAdjacentElement("afterend", topDivider);
    }
    styleInstalledDivider(topDivider, "0 0 1px");
  } else {
    delete document.documentElement.dataset.installedRealMosaic;
    topDivider?.remove();
  }

  if (!contentDivider) {
    contentDivider = document.createElement("div");
    contentDivider.dataset.installedMosaicDividerContent = "true";
    contentDivider.setAttribute("aria-hidden", "true");
    workbench.insertAdjacentElement("afterend", contentDivider);
  } else if (contentDivider.previousElementSibling !== workbench) {
    workbench.insertAdjacentElement("afterend", contentDivider);
  }

  if (installed) styleInstalledDivider(contentDivider, ".22rem 0 .26rem");
  else styleWebContentDivider(contentDivider, workbench);
}

syncMosaics();
requestAnimationFrame(syncMosaics);
setTimeout(syncMosaics, 250);
window.addEventListener("resize", syncMosaics);
window.addEventListener("orientationchange", syncMosaics);
window.addEventListener("appinstalled", syncMosaics);
standaloneQuery?.addEventListener?.("change", syncMosaics);
mobileQuery?.addEventListener?.("change", syncMosaics);
