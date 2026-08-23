import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const styles = readFileSync(new URL("./exhibition-compact.css", import.meta.url), "utf8");
const schedule = readFileSync(new URL("./schedule-display.js", import.meta.url), "utf8");

assert.match(
  styles,
  /--agenda-group-row-min-height:\s*96px;[\s\S]*?\.grouped-exhibition-item\s*\{[\s\S]*?height:\s*auto\s*!important;[\s\S]*?min-height:\s*var\(--agenda-group-row-min-height\)\s*!important;[\s\S]*?max-height:\s*none\s*!important;[\s\S]*?overflow:\s*visible\s*!important;/,
  "grouped exhibition rows must grow enough to show complete subcards instead of clipping enriched schedule/location text",
);

assert.match(
  styles,
  /--agenda-group-list-max-height:\s*306px;[\s\S]*?\.exhibition-group-list\s*\{[\s\S]*?max-height:\s*var\(--agenda-group-list-max-height\)\s*!important;/,
  "larger exhibition groups keep a bounded internal scroll",
);

assert.match(
  styles,
  /\.exhibition-group-list:not\(:has\(> \.grouped-exhibition-item:nth-child\(4\)\)\)\s*\{[\s\S]*?max-height:\s*none\s*!important;[\s\S]*?overflow-y:\s*visible\s*!important;/,
  "groups of up to three exhibitions must show every subcard completely without internal clipping",
);

assert.match(
  schedule,
  /\[data-exhibition-opening-hours\], \.exhibition-venue-hours/,
  "static and runtime venue-hours rows must share one selector",
);

assert.match(
  schedule,
  /candidates\.slice\(1\)[\s\S]*?duplicate\.remove\(\)/,
  "duplicate venue-hours rows must be removed structurally",
);

console.log("EXHIBITION_CARD_STRUCTURE_OK");
