import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/exhibition-hours.js", import.meta.url), "utf8");
const release = await readFile(new URL("../app/release-version.js", import.meta.url), "utf8");

test("MHNV grouped exhibition cards create a venue-hours slot when missing", () => {
  assert.match(source, /const MHNV_HOURS = "Mar–vie 10:00–18:00 · sáb 11:00–16:00 · dom\/lun\/festivos cerrado"/);
  assert.match(source, /card\.querySelector\("\.exhibition-venue-facts"\)/);
  assert.match(source, /node\.dataset\.exhibitionOpeningHours = ""/);
  assert.match(source, /facts\.append\(node\)/);
  assert.match(source, /groupedOpeningHoursNode\(card, Boolean\(hours\)\)/);
});

test("PWA release is renewed for grouped MHNV hours", () => {
  assert.match(release, /const RELEASE = 157;/);
});
