import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const source = readFileSync(new URL("./exhibition-groups.js", import.meta.url), "utf8");
assert.doesNotMatch(source, /partitionExhibitionsByDuration\(events, config\)/);
assert.match(source, /const id = String\(card\.dataset\.eventId \|\| ""\)\.trim\(\);[\s\S]*?if \(!id\) continue;/);
assert.match(source, /if \(!card\.dataset\.eventGroup \|\| card\.dataset\.unifiedExhibitionGroup === "true"\) continue;/);
console.log("EXHIBITION_GROUP_ARCHITECTURE_OK");
