import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("./exhibition-hours.js", import.meta.url), "utf8");

assert.match(
  source,
  /\.grouped-exhibition-item\s*\{[\s\S]*?height:\s*auto\s*!important;[\s\S]*?min-height:\s*96px\s*!important;[\s\S]*?max-height:\s*none\s*!important;[\s\S]*?overflow:\s*visible\s*!important;/,
  "grouped exhibition rows must grow enough to show complete subcards instead of clipping enriched schedule/location text",
);

assert.match(
  source,
  /\.exhibition-group-list\s*\{[\s\S]*?max-height:\s*306px\s*!important;/,
  "larger exhibition groups keep a bounded internal scroll",
);

assert.match(
  source,
  /\.exhibition-group-list:not\(:has\(> \.grouped-exhibition-item:nth-child\(4\)\)\)\s*\{[\s\S]*?max-height:\s*none\s*!important;[\s\S]*?overflow-y:\s*visible\s*!important;/,
  "groups of up to three exhibitions must show every subcard completely without internal clipping",
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
  /Three-item museum groups such as Palacio Rioja should show all three[\s\S]*?subcards completely/,
  "the approved three-complete-subcards design decision must remain documented in the implementation",
);

console.log("EXHIBITION_CARD_STRUCTURE_OK");
