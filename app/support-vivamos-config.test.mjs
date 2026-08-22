import test from "node:test";
import assert from "node:assert/strict";
import { SUPPORT_VIVAMOS, getEnabledSupportMethods } from "./support-vivamos-config.mjs";

test("support remains fully hidden by default", () => {
  assert.equal(SUPPORT_VIVAMOS.enabled, false);
  assert.deepEqual(getEnabledSupportMethods(), []);
});

test("configured support destinations are real https links while globally hidden", () => {
  assert.deepEqual(
    SUPPORT_VIVAMOS.methods.map(({ id, enabled, url }) => ({ id, enabled, url })),
    [
      {
        id: "mercadopago-cl",
        enabled: true,
        url: "https://link.mercadopago.cl/vivamos",
      },
      {
        id: "paypal-international",
        enabled: true,
        url: "https://www.paypal.com/ncp/payment/MMR5A78JMY5VL",
      },
    ],
  );
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
