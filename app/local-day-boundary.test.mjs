import assert from "node:assert/strict";
import test from "node:test";

import { localDayKey, millisecondsUntilNextLocalDay } from "./local-day-boundary.mjs";

test("finds the next local midnight independently for every city timezone", () => {
  const now = new Date("2026-08-23T23:30:00Z");
  assert.equal(localDayKey(now, "America/Santiago"), "2026-08-23");
  assert.equal(localDayKey(now, "Europe/Madrid"), "2026-08-24");
  assert.ok(Math.abs(millisecondsUntilNextLocalDay(now, "America/Santiago") - 16_200_000) < 2_000);
  assert.ok(Math.abs(millisecondsUntilNextLocalDay(now, "Europe/Madrid") - 81_000_000) < 2_000);
});

test("handles daylight-saving local days without assuming 24 hours", () => {
  const beforeChange = new Date("2026-09-05T23:30:00Z");
  const delay = millisecondsUntilNextLocalDay(beforeChange, "America/Santiago");
  const boundary = new Date(beforeChange.getTime() + delay);
  assert.notEqual(localDayKey(boundary, "America/Santiago"), localDayKey(beforeChange, "America/Santiago"));
});
