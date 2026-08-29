import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (name) => readFileSync(new URL(`./${name}`, import.meta.url), "utf8");

test("display-card counting is a pure derivative of canonical selection and the sole DOM owner", () => {
  const helper = read("visible-display-card-core.mjs");
  const combined = read("combined-filters.js");
  const selection = read("public-selection-core.mjs");
  const safety = read("combined-filters-safety.js");
  assert.doesNotMatch(helper, /document\.|querySelector|hidden\s*=/);
  assert.match(combined, /eventMatchesCanonicalSection/);
  assert.match(combined, /countDisplayCards/);
  assert.match(selection, /eventMatchesCanonicalSection/);
  assert.doesNotMatch(safety, /\.hidden\s*=/);
});

test("the released WEB and APP paths reference one versioned filter implementation", () => {
  const bootstrap = read("combined-filters-bootstrap.js");
  const parity = read("public-selection-parity.test.mjs");
  assert.match(bootstrap, /combined-filters\.js\?v=/);
  assert.match(parity, /APP filters/);
  assert.match(parity, /WEB/);
});
