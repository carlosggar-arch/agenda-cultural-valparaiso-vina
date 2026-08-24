import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const pipeline = readFileSync(new URL("./data-pipeline.js", import.meta.url), "utf8");

test("processed cache stores normalized data before runtime visibility is materialized", () => {
  const write = pipeline.indexOf("writeProcessedResult(city, payloadResult.sourceSignature, normalizedResult)");
  const materialize = pipeline.indexOf("materializeRuntimeResult(normalizedResult, city, now, diagnostics)");
  assert.ok(write >= 0 && materialize > write, "normalization must be cached before temporal visibility is applied");
  assert.doesNotMatch(pipeline, /day:\s*localDateKey|removeExpiredDatedEvents/, "cache identity and contents must be time-independent");
  assert.match(pipeline, /materializeRuntimeResult\(cached, city, now, diagnostics\)/, "cache hits must re-evaluate visibility using the current reference time");
});
