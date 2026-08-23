import assert from "node:assert/strict";
import test from "node:test";

import { createReleaseHandoff } from "./pwa-release-handoff.mjs";

test("first service-worker control does not reload a newly installed App", () => {
  const handoff = createReleaseHandoff(false);
  assert.equal(handoff.controllerChanged(), false);
});

test("replacing an existing controller reloads exactly once", () => {
  const handoff = createReleaseHandoff(true);
  assert.equal(handoff.controllerChanged(), true);
  assert.equal(handoff.controllerChanged(), false);
});
