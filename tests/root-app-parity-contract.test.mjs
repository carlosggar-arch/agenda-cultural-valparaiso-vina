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
  assert.match(runtime, /data-result-line/);
  assert.match(runtime, /data-total/);
  assert.doesNotMatch(runtime, /import\("\.\/agenda\.js/);
  assert.doesNotMatch(runtime, /import\("\.\/web-event-enhancements\.js/);
});

test("root parity adapter loads before the existing WEB renderers", async () => {
  const index = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const parity = index.indexOf("root-app-parity-runtime.mjs");
  const agenda = index.indexOf("./assets/agenda.js");
  const enhancements = index.indexOf("./assets/web-event-enhancements.js");
  assert.ok(parity >= 0, "root parity runtime must be present");
  assert.ok(agenda > parity, "agenda.js must load after parity runtime");
  assert.ok(enhancements > agenda, "web-event-enhancements.js must load after agenda.js");
});
