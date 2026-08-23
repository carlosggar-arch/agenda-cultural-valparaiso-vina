import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("./map-navigation-enhancer.js", import.meta.url), "utf8");
const indexSource = readFileSync(new URL("./index.html", import.meta.url), "utf8");
const releaseSource = readFileSync(new URL("./release-version.js", import.meta.url), "utf8");

assert.match(source, /vivamos-map-navigation-styles/, "map navigation must own one shared style contract");
assert.match(source, /box-sizing:border-box/, "the visible Maps control must include its border inside the requested dimensions");
assert.match(source, /width:25px/, "map arrow control must be exactly 25 px wide");
assert.match(source, /height:25px/, "map arrow control must be exactly 25 px high");
assert.match(source, /border-radius:4px/, "map arrow must keep a compact rounded clickable surround");
assert.match(source, /\.map-location-link-icon\s*\{[\s\S]*width:18px;[\s\S]*height:18px;/, "map arrow icon box must be 18 px by 18 px");
assert.match(source, /viewBox", "0 0 18 18"/, "map arrow SVG must use an 18 px design box");
assert.match(source, /stroke-width", "2\.2"/, "map arrow stroke must remain legible at 18 px");
assert.match(source, /background:color-mix/, "map arrow must have a visible interactive background");
assert.match(source, /card-fact--map-location/, "location rows must receive their own alignment hook");
assert.match(source, /align-items:center !important/, "location icon and text must be vertically centered");
assert.match(source, /margin-top:0 !important/, "location icon must not retain the old offset mismatch");
assert.match(source, /link\.removeAttribute\("style"\)/, "legacy inline map styles must not override the shared pill contract");
assert.match(source, /link\.replaceChildren\(makeMapIcon\(\)\)/, "legacy text arrows must be upgraded to the shared 18 px icon");
assert.match(source, /focus-visible/, "map arrow must retain a visible keyboard focus state");

const release = releaseSource.match(/const\s+RELEASE\s*=\s*(\d+)/)?.[1];
const mapAssetVersion = indexSource.match(/map-navigation-enhancer\.js\?v=(\d+)/)?.[1];
assert.ok(release, "shared PWA release must be declared");
assert.equal(mapAssetVersion, release, "Maps module cache key must match the current PWA release");

console.log("MAP_NAVIGATION_ENHANCER_CONTRACT_OK");
