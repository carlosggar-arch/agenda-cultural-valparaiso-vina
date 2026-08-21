import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const current = JSON.parse(await readFile(new URL("../../fuentes_publicas.json", import.meta.url), "utf8"));
const baselinePath = String(process.env.PUBLIC_SOURCES_BASELINE || "").trim();

function identity(source) {
  const canonical = String(source?.canonical_source_id || "").trim().toLowerCase();
  if (canonical) return `canonical:${canonical}`;
  const publicId = String(source?.id || "").trim().toLowerCase();
  assert.ok(publicId, `source without stable identity: ${JSON.stringify(source)}`);
  return `public:${publicId}`;
}

function byIdentity(payload) {
  const map = new Map();
  for (const source of payload?.sources || []) {
    const key = identity(source);
    assert.ok(!map.has(key), `duplicate public source identity: ${key}`);
    map.set(key, source);
  }
  return map;
}

test("previously published public sources cannot disappear", async (t) => {
  if (!baselinePath) {
    t.skip("PUBLIC_SOURCES_BASELINE is only supplied by the regression workflow");
    return;
  }
  const baseline = JSON.parse(await readFile(baselinePath, "utf8"));
  const before = byIdentity(baseline);
  const after = byIdentity(current);
  const missing = [...before.entries()]
    .filter(([key]) => !after.has(key))
    .map(([key, source]) => `${source?.name || key} [${key}]`)
    .sort();
  assert.deepEqual(
    missing,
    [],
    `previously published sources disappeared: ${missing.join(", ")}`,
  );
});
