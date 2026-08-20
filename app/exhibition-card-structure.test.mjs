import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("./exhibition-hours.js", import.meta.url), "utf8");

assert.match(
  source,
  /\.grouped-exhibition-item\s*\{[\s\S]*?height:\s*auto\s*!important;[\s\S]*?min-height:\s*84px\s*!important;[\s\S]*?max-height:\s*none\s*!important;/,
  "grouped exhibition rows must grow enough to show a complete subcard instead of clipping it",
);

assert.doesNotMatch(
  source,
  /\.exhibition-group-list\s*\{[\s\S]*?max-height:\s*(?:216|222|228)px\s*!important;/,
  "the recovery must not enlarge the whole grouped card just to force three rows into view",
);

assert.match(
  source,
  /\[data-exhibition-opening-hours\], \.exhibition-venue-hours/,
  "static and runtime venue-hours rows must share one selector",
);

assert.match(
  source,
  /candidates\.slice\(1\)[\s\S]*?duplicate\.remove\(\)/,
  "duplicate venue-hours rows must be removed structurally",
);

assert.match(
  source,
  /Two complete rows are preferable to[\s\S]*?three cropped rows/,
  "the compact two-complete-rows design decision must remain documented in the implementation",
);

console.log("EXHIBITION_CARD_STRUCTURE_OK");
