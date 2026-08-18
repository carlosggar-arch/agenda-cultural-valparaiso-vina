import "./exhibition-compact.js?v=20260818-compact5";

const STYLE_ID = "exhibition-compact-styles";
const STYLE_URL = new URL("./exhibition-compact.css?v=20260818-compact5", import.meta.url).href;

function activateSafeLayout() {
  let link = document.getElementById(STYLE_ID);
  if (!link) {
    link = document.createElement("link");
    link.id = STYLE_ID;
    link.rel = "stylesheet";
    document.head.append(link);
  }
  if (link.href !== STYLE_URL) link.href = STYLE_URL;
}

activateSafeLayout();
requestAnimationFrame(activateSafeLayout);
