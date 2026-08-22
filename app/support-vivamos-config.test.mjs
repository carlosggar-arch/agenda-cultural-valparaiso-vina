import test from "node:test";
import assert from "node:assert/strict";
import { SUPPORT_VIVAMOS, getEnabledSupportMethods } from "./support-vivamos-config.mjs";

test("support remains fully hidden by default", () => {
  assert.equal(SUPPORT_VIVAMOS.enabled, false);
  assert.deepEqual(getEnabledSupportMethods(), []);
});

test("support methods require both enablement and https destination", () => {
  const config = {
    enabled: true,
    methods: [
      { enabled: true, url: null },
      { enabled: true, url: "http://example.com" },
      { enabled: false, url: "https://example.com/off" },
      { enabled: true, url: "https://example.com/on" },
    ],
  };
  assert.deepEqual(getEnabledSupportMethods(config), [config.methods[3]]);
});
