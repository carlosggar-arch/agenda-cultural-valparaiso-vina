import test from "node:test";
import assert from "node:assert/strict";

import {
  buildReminderIcs,
  reminderFilename,
  reminderOptionsForEvent,
} from "../assets/favorites-reminders.mjs";

const timedEvent = {
  id: "media-maraton-tps",
  title: "Media Maratón TPS, Valparaíso",
  schedule: {
    start: "2026-09-06T08:30:00-04:00",
    end: "2026-09-06T12:00:00-04:00",
  },
  location: {
    venue: "Muelle Prat",
    city: "Valparaíso",
  },
};

test("offers only reminders that are still useful", () => {
  const now = new Date("2026-08-17T12:00:00-04:00");
  assert.deepEqual(reminderOptionsForEvent(timedEvent, now).map((item) => item.id), ["2h", "1d"]);
  assert.deepEqual(reminderOptionsForEvent(timedEvent, new Date("2026-09-06T07:00:00-04:00")), []);
});

test("builds a timed calendar event with a one-day VALARM", () => {
  const ics = buildReminderIcs({
    city: "valparaiso",
    event: timedEvent,
    pageUrl: "https://example.test/evento/valparaiso/media-maraton-tps/",
    lead: "1d",
    now: new Date("2026-08-17T16:00:00Z"),
  });
  assert.ok(ics);
  assert.match(ics, /BEGIN:VALARM/);
  assert.match(ics, /TRIGGER:-P1D/);
  assert.match(ics, /DTSTART:20260906T123000Z/);
  assert.match(ics, /DTEND:20260906T160000Z/);
  assert.match(ics, /SUMMARY:Media Maratón TPS\\, Valparaíso/);
  assert.match(ics, /LOCATION:Muelle Prat · Valparaíso/);
  assert.match(ics, /URL:https:\/\/example\.test\/evento\/valparaiso\/media-maraton-tps\//);
});

test("builds a two-hour reminder for timed events", () => {
  const ics = buildReminderIcs({ city: "valparaiso", event: timedEvent, lead: "2h" });
  assert.match(ics, /TRIGGER:-PT2H/);
});

test("all-day activities use DATE values and only offer one-day reminders", () => {
  const event = {
    id: "festival",
    title: "Festival de barrio",
    schedule: { start: "2026-10-04" },
  };
  const options = reminderOptionsForEvent(event, new Date("2026-08-17T12:00:00-04:00"));
  assert.deepEqual(options.map((item) => item.id), ["1d"]);
  const ics = buildReminderIcs({ city: "valparaiso", event, lead: "1d" });
  assert.match(ics, /DTSTART;VALUE=DATE:20261004/);
  assert.match(ics, /DTEND;VALUE=DATE:20261005/);
});

test("events without a usable date do not get reminders", () => {
  assert.deepEqual(reminderOptionsForEvent({ title: "Sin fecha" }, new Date("2026-08-17T12:00:00Z")), []);
  assert.equal(buildReminderIcs({ city: "valparaiso", event: { title: "Sin fecha" }, lead: "1d" }), null);
});

test("uses a safe descriptive .ics filename", () => {
  assert.equal(reminderFilename(timedEvent), "recordatorio-media-maraton-tps-valparaiso.ics");
});
