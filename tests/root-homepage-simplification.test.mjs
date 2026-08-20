import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("homepage hides featured and detailed filter blocks", async () => {
  const css = await readFile(new URL("../assets/accessibility.css", import.meta.url), "utf8");
  assert.match(css, /#destacados/);
  assert.match(css, /#categorias/);
  assert.match(css, /data-section="destacados"/);
  assert.match(css, /display:\s*none\s*!important/);
});
