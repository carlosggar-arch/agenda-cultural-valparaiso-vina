import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const participationFooter = await readFile(
  new URL("../app/participation-footer.js", import.meta.url),
  "utf8",
);
const exhibitionHours = await readFile(
  new URL("../app/exhibition-hours.js", import.meta.url),
  "utf8",
);
const appShell = await readFile(
  new URL("../app/app.js", import.meta.url),
  "utf8",
);

test("delayed participation footer never deletes Fuentes access", () => {
  assert.doesNotMatch(
    participationFooter,
    /querySelector\(["']\[data-sources-toggle\]["']\)\?\.remove\(\)/,
  );
  assert.match(participationFooter, /data-sources-toggle/);
  assert.match(participationFooter, /data-sources-fallback/);
  assert.match(appShell, /ensureSourcesFallbackLink/);
});

test("MHNV multi-day exhibitions have official weekly visit hours", () => {
  assert.match(exhibitionHours, /museo de historia natural de valparaiso/);
  assert.match(
    exhibitionHours,
    /Mar–vie 10:00–18:00 · sáb 11:00–16:00 · dom\/lun\/festivos cerrado/,
  );
  assert.match(exhibitionHours, /isMultiDayVisit/);
  assert.match(exhibitionHours, /knownVenueHours/);
});
