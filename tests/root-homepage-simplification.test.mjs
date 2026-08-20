import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("homepage hides redundant discovery blocks", async () => {
  const css = await readFile(new URL("../assets/accessibility.css", import.meta.url), "utf8");
  assert.match(css, /#destacados/);
  assert.match(css, /#categorias/);
  assert.match(css, /#explorar\s+\.explore-heading/);
  assert.match(css, /#explorar\s+\.section-tabs/);
  assert.match(css, /data-section="destacados"/);
  assert.match(css, /display:\s*none\s*!important/);
});
