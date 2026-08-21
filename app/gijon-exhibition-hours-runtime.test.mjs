import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const app = readFileSync(new URL("./app.js", import.meta.url), "utf8");

const optionalBlock = app.match(/const OPTIONAL_MODULES = \[([\s\S]*?)\];/)?.[1] || "";
const gijonDeferredBlock = app.match(/const GIJON_DEFERRED_MODULES = new Set\(\[([\s\S]*?)\]\);/)?.[1] || "";
const nonGijonBlock = app.match(/\} else \{([\s\S]*?)\n\}/)?.[1] || "";

assert.match(
  optionalBlock,
  /exhibition-hours\.js/,
  "exhibition-hours must load from the common runtime so grouped Gijon exhibitions receive venue hours",
);
assert.doesNotMatch(
  gijonDeferredBlock,
  /exhibition-hours\.js/,
  "Gijon must not defer exhibition-hours",
);
assert.doesNotMatch(
  nonGijonBlock,
  /exhibition-hours\.js/,
  "exhibition-hours must not be owned only by the non-Gijon runtime",
);

console.log("GIJON_EXHIBITION_HOURS_SHARED_RUNTIME_OK");
