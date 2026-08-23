import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("./map-navigation-enhancer.js", import.meta.url), "utf8");

assert.match(source, /vivamos-map-navigation-styles/, "map navigation must own one shared style contract");
assert.match(source, /border-radius:\.34rem/, "map arrow must keep a compact rounded clickable surround");
assert.match(source, /height:\.94rem/, "map arrow control must stay shorter than the location text line");
assert.match(source, /width:1\.08rem/, "map arrow control must remain visually discreet");
assert.match(source, /background:color-mix/, "map arrow must have a visible interactive background");
assert.match(source, /card-fact--map-location/, "location rows must receive their own alignment hook");
assert.match(source, /align-items:center !important/, "location icon and text must be vertically centered");
assert.match(source, /margin-top:0 !important/, "location icon must not retain the old offset mismatch");
assert.match(source, /link\.removeAttribute\("style"\)/, "legacy inline map styles must not override the shared pill contract");
assert.match(source, /focus-visible/, "map arrow must retain a visible keyboard focus state");

console.log("MAP_NAVIGATION_ENHANCER_CONTRACT_OK");
