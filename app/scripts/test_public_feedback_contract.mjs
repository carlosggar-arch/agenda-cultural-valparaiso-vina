import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const read = (relative) => fs.readFileSync(path.join(app, relative), "utf8");

const community = read("community-source.js");
const css = read("community-source.css");
const pwa = read("pwa.js");
const worker = read("service-worker.js");
const release = read("release-version.js");

for (const marker of ["+ Aportar fuente", "Comentarios", "data-community-like", "FEEDBACK_API", "/likes", "/comments"]) {
  assert.match(community, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
}
assert.match(community, /community-source\.css\?v=20260818-feedback2/);
assert.match(pwa, /community-source\.js\?v=20260818-feedback2/);
assert.match(worker, /community-source\.js\?v=20260818-feedback2/);
assert.match(worker, /community-source\.css\?v=20260818-feedback2/);
assert.match(css, /\.source-proposal-actions\{[^}]*flex-wrap:nowrap/s);
assert.match(css, /@media\(max-width:700px\)[\s\S]*\.source-proposal-actions\{[^}]*overflow-x:auto/s);
assert.doesNotMatch(css, /@media\(max-width:700px\)[\s\S]*\.source-proposal-cta\{[^}]*flex-direction:column/s);
assert.match(release, /const RELEASE = 97/);

console.log("Public feedback WEB + PWA single-row contract: OK");
