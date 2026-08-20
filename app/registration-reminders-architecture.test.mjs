import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const app = await readFile(new URL("./app.js", import.meta.url), "utf8");
const component = await readFile(new URL("./registration-reminders.js", import.meta.url), "utf8");
const pipeline = await readFile(new URL("./data-pipeline.js", import.meta.url), "utf8");
const classifier = await readFile(new URL("./formation-cycle-classifier.js", import.meta.url), "utf8");
const serviceWorker = await readFile(new URL("./service-worker.js", import.meta.url), "utf8");

assert.match(classifier, /event_type:\s*"registration_period"/, "registration reminders need a semantic event type");
assert.match(classifier, /enrollment_or_booking_process_not_single_event/, "classification must record why the item is not a normal event");
assert.match(pipeline, /formation-lifecycle-classifier/, "the common pipeline must own lifecycle classification for every city");
assert.match(app, /registration-reminders\.js\?v=20260820-registration1/, "the shared app shell must load the common reminder component");
assert.match(component, /Inscripciones y plazos/, "the common component must expose a dedicated registration section");
assert.match(component, /data-registration-grid/, "registration reminders need their own grid");
assert.match(component, /event-card--registration/, "registration reminders need a distinct presentation class");
assert.match(component, /getAgendaRuntimeSnapshot/, "the component must consume the normalized shared runtime rather than rereading city datasets");
assert.match(component, /agenda\.insertBefore\(section, programSection\)/, "registration reminders should sit between dated events and long programs");
assert.match(component, /const activityTotal = dated \+ program \+ flexible/, "reminders must not inflate the cultural-event total");
assert.doesNotMatch(component, /IS_GIJON|cityId\s*===\s*["']gijon["']/, "registration presentation must be city-agnostic");
assert.match(serviceWorker, /registration-reminders\.js\?v=20260820-registration1/, "the common reminder component must work offline too");

console.log("REGISTRATION_REMINDERS_ARCHITECTURE_OK");
