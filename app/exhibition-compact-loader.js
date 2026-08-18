// Stability-first loader: keep the compact exhibition CSS, but do not execute
// exhibition-compact.js in the browser. The previous runtime observed class,
// hidden and src mutations across every event grid and could enter a feedback
// loop as lazy images loaded while scrolling. Exhibition grouping remains handled
// by exhibition-venue-grouping.js; this file is now presentation-only.

const STYLE_ID = "exhibition-compact-styles";
const STYLE_URL = new URL("./exhibition-compact.css?v=20260818-compact8", import.meta.url).href;

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
