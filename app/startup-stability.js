const STYLE_ID = "vivamos-startup-stability";

function installStartupStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    html:not([data-vivamos-ready="true"]) main > .status,
    html:not([data-vivamos-ready="true"]) main > .discovery,
    html:not([data-vivamos-ready="true"]) main > .agenda {
      visibility: hidden !important;
    }
  `;
  document.head.append(style);
}

function currentUiReady() {
  const agenda = document.querySelector("[data-agenda]");
  const chooser = document.querySelector("[data-chooser-backdrop]");
  return Boolean((agenda && !agenda.hidden) || (chooser && !chooser.hidden));
}

function revealWhenReady() {
  if (!currentUiReady()) return false;
  document.documentElement.dataset.vivamosReady = "true";
  return true;
}

installStartupStyle();
if (!revealWhenReady()) {
  const observer = new MutationObserver(() => {
    if (revealWhenReady()) observer.disconnect();
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["hidden"],
  });
  window.setTimeout(() => {
    document.documentElement.dataset.vivamosReady = "true";
    observer.disconnect();
  }, 8000);
}
