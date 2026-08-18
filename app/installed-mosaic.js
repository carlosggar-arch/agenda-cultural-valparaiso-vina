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
  `;
  document.head.append(style);
  return style;
}

function syncInstalledMosaic() {
  let divider = document.querySelector("[data-installed-mosaic-divider]");

  if (!isInstalledMobile()) {
    delete document.documentElement.dataset.installedRealMosaic;
    divider?.remove();
    return;
  }

  const header = document.querySelector(".app-header");
  if (!header) return;

  ensureMosaicOverrideStyle();
  document.documentElement.dataset.installedRealMosaic = "true";

  if (!divider) {
    divider = document.createElement("div");
    divider.dataset.installedMosaicDivider = "true";
    divider.setAttribute("aria-hidden", "true");
    header.insertAdjacentElement("afterend", divider);
  } else if (divider.previousElementSibling !== header) {
    header.insertAdjacentElement("afterend", divider);
  }

  divider.style.setProperty("display", "block", "important");
  divider.style.setProperty("position", "relative", "important");
  divider.style.setProperty("z-index", "20", "important");
  divider.style.setProperty("box-sizing", "border-box", "important");
  divider.style.setProperty("width", "calc(100% - 2rem)", "important");
  divider.style.setProperty("height", "15px", "important");
  divider.style.setProperty("min-height", "15px", "important");
  divider.style.setProperty("max-height", "15px", "important");
  divider.style.setProperty("margin", "-8px auto 1px", "important");
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

syncInstalledMosaic();
requestAnimationFrame(syncInstalledMosaic);
window.addEventListener("resize", syncInstalledMosaic);
window.addEventListener("orientationchange", syncInstalledMosaic);
window.addEventListener("appinstalled", syncInstalledMosaic);
standaloneQuery?.addEventListener?.("change", syncInstalledMosaic);
mobileQuery?.addEventListener?.("change", syncInstalledMosaic);
