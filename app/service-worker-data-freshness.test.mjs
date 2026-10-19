import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("./service-worker.js", import.meta.url), "utf8");

test("published agenda datasets are network-first with cached offline fallback", () => {
  const fn = source.slice(
    source.indexOf("async function networkFirstDataset"),
    source.indexOf('self.addEventListener("fetch"'),
  );
  const network = fn.indexOf("fetchAndCacheDataset(cache, request)");
  const cached = fn.indexOf("cache.match(request");
  assert.ok(network >= 0, "dataset path must attempt network fetch");
  assert.ok(cached > network, "cached dataset must be consulted only after network failure");
  assert.doesNotMatch(fn, /event\.waitUntil\(fetchAndCacheDataset/, "dataset path must not return stale data while merely refreshing in background");
  assert.match(source, /return networkFirstDataset\(request\);/);
  assert.doesNotMatch(source, /return cacheFirstDataset\(request, event\);/);
});
