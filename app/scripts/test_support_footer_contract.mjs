import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync(new URL("../participation-footer.js", import.meta.url), "utf8");

assert.match(source, /const SUPPORT_LABEL = "❤️ Apoya ¡Vivamos!";/);
assert.match(source, /const SUPPORT_PAYPAL_URL = "https:\/\/www\.paypal\.com\/ncp\/payment\/MMR5A78JMY5VL";/);
assert.match(source, /link\.href = SUPPORT_PAYPAL_URL;/);
assert.match(source, /link\.target = "_blank";/);
assert.match(source, /link\.rel = "noopener noreferrer";/);
assert.match(source, /data-sources-toggle/);
assert.match(source, /data-sources-fallback/);
assert.match(source, /dataset\.vivamosSupport/);
assert.doesNotMatch(source, /mercadopago/i);
assert.doesNotMatch(source, /aria-haspopup|role", "menu|support-menu/i);

console.log("SUPPORT_FOOTER_CONTRACT_OK provider=PayPal placement=footer-near-sources");
