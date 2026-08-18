import assert from "node:assert/strict";
import fs from "node:fs";

const js = fs.readFileSync(new URL("../app/community-source.js", import.meta.url), "utf8");
const css = fs.readFileSync(new URL("../app/community-source.css", import.meta.url), "utf8");
const pwa = fs.readFileSync(new URL("../app/pwa.js", import.meta.url), "utf8");

assert.match(js, /data-source-proposal-link/);
assert.match(js, /data-community-comments/);
assert.match(js, /data-community-like/);
assert.match(js, /community\/v1\/feedback/);
assert.match(js, /vivamos-global-like-token-v1/);
assert.match(js, /pending_review/);
assert.match(js, /Comentario recibido/);
assert.match(css, /\.source-proposal-actions\{[^}]*display:flex[^}]*flex-wrap:nowrap/s);
assert.match(css, /\.source-proposal-actions\{[^}]*gap:/s);
assert.doesNotMatch(css, /\.source-proposal-actions\{[^}]*flex-direction:\s*column/s);
assert.match(css, /@media\(max-width:700px\)[\s\S]*\.source-proposal-actions\{[^}]*overflow-x:auto/s);
assert.match(css, /\.source-action-short\{display:none\}/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback1/);

console.log("Community feedback UI contract: one action row with source, comments and like counter");
