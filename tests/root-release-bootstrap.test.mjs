import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("root WEB cache invalidation derives from the canonical release", async () => {
  const index = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const bootstrap = await readFile(new URL("../assets/root-agenda-bootstrap.mjs", import.meta.url), "utf8");
  assert.match(index, /<script src="\.\/app\/release-version\.js"><\/script>/);
  assert.match(index, /src="\.\/assets\/root-agenda-bootstrap\.mjs"/);
  assert.doesNotMatch(index, /assets\/agenda\.js\?v=/);
  assert.match(bootstrap, /globalThis\.__VIVAMOS_RELEASE__/);
  assert.match(bootstrap, /import\(`\.\/agenda\.js\?v=\$\{release\}`\)/);
});

test("WEB and App consume the canonical event-image renderer", async () => {
  const web = await readFile(new URL("../assets/agenda.js", import.meta.url), "utf8");
  const app = await readFile(new URL("../app/card-experience.js", import.meta.url), "utf8");
  for (const source of [web, app]) {
    assert.match(source, /event-image-renderer\.mjs/);
    assert.match(source, /createEventImageElement/);
  }
});

test("WEB result count has one mutation owner", async () => {
  const parity = await readFile(new URL("../assets/root-app-parity-runtime.mjs", import.meta.url), "utf8");
  const enhancements = await readFile(new URL("../assets/web-event-enhancements.js", import.meta.url), "utf8");
  assert.match(parity, /total\.textContent = match\[1\]/);
  assert.doesNotMatch(enhancements, /setTextIfChanged\(total,/);
});
