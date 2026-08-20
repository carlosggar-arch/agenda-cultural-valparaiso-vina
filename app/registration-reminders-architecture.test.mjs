import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const app = await readFile(new URL("./app.js", import.meta.url), "utf8");
const pipeline = await readFile(new URL("./data-pipeline.js", import.meta.url), "utf8");
const classifier = await readFile(new URL("./formation-cycle-classifier.js", import.meta.url), "utf8");

assert.match(classifier, /event_type:\s*"registration_period"/, "registration reminders need a semantic event type");
assert.match(classifier, /enrollment_or_booking_process_not_single_event/, "classification must record why the item is not a normal event");
assert.match(pipeline, /formation-lifecycle-classifier/, "the common pipeline must own lifecycle classification for every city");
assert.match(app, /Inscripciones y plazos/, "the shared app shell must expose a dedicated registration section");
assert.match(app, /data-registration-grid/, "registration reminders need their own grid");
assert.match(app, /event-card--registration/, "registration reminders need a distinct presentation class");
assert.match(app, /getAgendaRuntimeSnapshot/, "the section must consume the normalized shared runtime rather than rereading city datasets");
assert.match(app, /agenda\.insertBefore\(section, programSection\)/, "registration reminders should sit between dated events and long programs");
assert.doesNotMatch(
  app.slice(app.indexOf("// Registration reminders")),
  /if\s*\(\s*IS_GIJON\s*\)/,
  "registration presentation must be city-agnostic",
);

console.log("REGISTRATION_REMINDERS_ARCHITECTURE_OK");
