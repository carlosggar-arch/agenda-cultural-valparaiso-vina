import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("root WEB consumes APP publication logic through a root-only adapter", async () => {
  const adapter = await readFile(new URL("../assets/root-app-parity-data.mjs", import.meta.url), "utf8");
  const runtime = await readFile(new URL("../assets/root-app-parity-runtime.mjs", import.meta.url), "utf8");
  assert.match(adapter, /\.\.\/app\/data-pipeline\.js/);
  assert.match(adapter, /supplemental-events\.json/);
  assert.match(runtime, /loadRootPublicDataset/);
  assert.match(runtime, /agenda_web\.json/);
});

test("root WEB keeps its own renderer and synchronizes the headline count with visible results", async () => {
  const runtime = await readFile(new URL("../assets/root-app-parity-runtime.mjs", import.meta.url), "utf8");
  assert.match(runtime, /import\("\.\/agenda\.js/);
  assert.match(runtime, /import\("\.\/web-event-enhancements\.js/);
  assert.match(runtime, /data-result-line/);
  assert.match(runtime, /data-total/);
});

test("root entrypoint is the root-only parity runtime", async () => {
  const index = await readFile(new URL("../index.html", import.meta.url), "utf8");
  assert.match(index, /root-app-parity-runtime\.mjs/);
  assert.doesNotMatch(index, /<script type="module" src="\.\/assets\/agenda\.js/);
  assert.doesNotMatch(index, /<script type="module" src="\.\/assets\/web-event-enhancements\.js/);
});
