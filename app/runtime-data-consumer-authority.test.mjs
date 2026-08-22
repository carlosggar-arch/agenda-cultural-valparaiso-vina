import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const favorites = read("./favorites.js");
const sources = read("./sources-toggle.js");
const app = read("./app.js");

assert.match(
  favorites,
  /getAgendaRuntimeSnapshot/,
  "favorites must consume the canonical runtime snapshot",
);
assert.match(
  favorites,
  /vivamos:agenda-data-ready/,
  "favorites must refresh when the canonical runtime publishes a new city snapshot",
);
assert.doesNotMatch(
  favorites,
  /\bfetch\s*\(/,
  "favorites must never download or parse the agenda dataset independently",
);
assert.doesNotMatch(
  favorites,
  /cache\s*:\s*["']no-store["']/,
  "favorites must not bypass the shared dataset authority with a private no-store request",
);

assert.match(
  sources,
  /getAgendaRuntimeSnapshot/,
  "sources must consume the canonical runtime snapshot",
);
assert.match(
  sources,
  /vivamos:agenda-data-ready/,
  "sources must refresh from the canonical snapshot after a city dataset is published",
);
assert.doesNotMatch(
  sources,
  /\bDATASETS\b|datasetUrl|fetchJson\s*\(/,
  "sources must not maintain a second city-dataset loader",
);
assert.match(
  sources,
  /PUBLIC_CATALOGUES/,
  "sources may still load the independent public source catalogue",
);
assert.match(
  sources,
  /loadPublicCatalogue/,
  "the supplementary source catalogue fetch must be explicit and isolated",
);
assert.equal(
  (sources.match(/\bfetch\s*\(/g) || []).length,
  1,
  "sources may issue exactly one fetch path: the supplementary public catalogue, never the agenda dataset",
);

assert.match(
  app,
  /sources-toggle\.js\?v=20260822-runtime-snapshot1/,
  "the shell must version the E2 sources consumer so stale optional-module caches cannot retain the old dataset loader",
);

console.log("RUNTIME_DATA_CONSUMER_AUTHORITY_OK favorites=shared sources=shared supplementary_catalogue=isolated");
