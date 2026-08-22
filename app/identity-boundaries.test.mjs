import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  areProbableDuplicateEvents,
  deduplicateCrossSourceDataset,
  mergeDuplicateEvents,
} from "./cross-source-deduplication.mjs";
import {
  sameLocalOccurrenceDate,
  sameLocalOccurrenceStart,
} from "./occurrence-identity-core.mjs";
import { groupStandaloneExhibitions } from "./exhibition-group-core.mjs";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const orchestrator = read("./cross-source-deduplication.mjs");
const eventIdentity = read("./event-identity-core.mjs");
const occurrenceIdentity = read("./occurrence-identity-core.mjs");
const visualGrouping = read("./exhibition-group-core.mjs");

function event(overrides = {}) {
  return {
    id: "event-a",
    event_type: "event",
    title: "Concierto de cámara",
    source_id: "source-a",
    source_name: "Fuente A",
    source_url: "https://a.example/event",
    organizer: "Fuente A",
    location: { venue: "Teatro Municipal", city: "Valparaíso", address: "Calle 1" },
    schedule: {
      start: "2026-08-22T19:00:00-04:00",
      end: "2026-08-22T20:00:00-04:00",
      occurrences: [],
    },
    links: { source: "https://a.example/event" },
    public_status: {},
    categories: [{ id: "musica", label: "Música" }],
    tags: [],
    image: { url: "https://a.example/image.jpg" },
    editorial: {},
    ...overrides,
  };
}

const sameSource = event({ id: "same-source-b", title: "Concierto cámara" });
assert.equal(areProbableDuplicateEvents(event(), sameSource), false, "same source must never cross-source dedupe");

const differentSource = event({
  id: "event-b",
  source_id: "source-b",
  source_name: "Fuente B",
  source_url: "https://b.example/event",
  links: { source: "https://b.example/event" },
  title: "Concierto de cámara",
});
assert.equal(sameLocalOccurrenceStart(event(), differentSource), true);
assert.equal(areProbableDuplicateEvents(event(), differentSource), true, "same start + venue + similar title across sources must dedupe");

const recurringA = event({
  title: "Taller de cerámica todos los sábados",
  public_status: { source_official: true },
});
const recurringB = event({
  id: "recurring-b",
  source_id: "source-b",
  source_name: "Fuente B",
  source_url: "https://b.example/recurring",
  links: { source: "https://b.example/recurring" },
  title: "Taller de cerámica sábado",
  schedule: { start: "2026-08-22T19:45:00-04:00", end: "2026-08-22T20:45:00-04:00", occurrences: [] },
});
assert.equal(sameLocalOccurrenceDate(recurringA, recurringB), true);
assert.equal(areProbableDuplicateEvents(recurringA, recurringB), true, "authoritative recurring titles within 60 minutes must preserve conflict reconciliation");

const recurringFar = event({
  ...recurringB,
  id: "recurring-far",
  schedule: { start: "2026-08-22T20:30:00-04:00", end: "2026-08-22T21:30:00-04:00", occurrences: [] },
});
assert.equal(areProbableDuplicateEvents(recurringA, recurringFar), false, "schedule conflicts beyond 60 minutes must remain distinct");

const multiOccurrenceA = event({
  schedule: {
    start: "2026-08-21T18:00:00-04:00",
    occurrences: [
      { start: "2026-08-21T18:00:00-04:00", end: "2026-08-21T19:00:00-04:00" },
      { start: "2026-08-23T18:00:00-04:00", end: "2026-08-23T19:00:00-04:00" },
    ],
  },
});
const multiOccurrenceB = event({
  id: "multi-b",
  source_id: "source-b",
  source_name: "Fuente B",
  source_url: "https://b.example/multi",
  links: { source: "https://b.example/multi" },
  schedule: { start: "2026-08-23T18:03:00-04:00", occurrences: [] },
});
assert.equal(sameLocalOccurrenceStart(multiOccurrenceA, multiOccurrenceB), true, "any matching occurrence must preserve semantic matching");
assert.equal(areProbableDuplicateEvents(multiOccurrenceA, multiOccurrenceB), true);

const secondaryBetterDescription = differentSource;
const officialPrimary = event({
  id: "official-a",
  public_status: { source_official: true, price_confirmed: true },
  schedule: {
    start: "2026-08-22T19:00:00-04:00",
    end: "2026-08-22T20:00:00-04:00",
    occurrences: [{ start: "2026-08-22T19:00:00-04:00", end: "2026-08-22T20:00:00-04:00" }],
  },
  image: { url: "https://a.example/official-image.jpg" },
});
const merged = mergeDuplicateEvents(officialPrimary, secondaryBetterDescription);
assert.equal(merged.id, "official-a", "quality-selected primary identity must remain the event identity");
assert.deepEqual(merged.schedule, officialPrimary.schedule, "occurrences/schedule must remain exactly the primary schedule");
assert.equal(merged.source_id, officialPrimary.source_id);
assert.equal(merged.source_url, officialPrimary.source_url);
assert.equal(merged.image.url, officialPrimary.image.url, "C8a must preserve the historical image merge policy for C8b");
assert.deepEqual(merged.editorial.merged_duplicate_ids, ["official-a", "event-b"]);
assert.equal(merged.editorial.cross_source_deduplicated, true);

const dataset = {
  counts: { total: 2, events: 2, courses: 0, flexible_offers: 0, programs: 0 },
  events: [officialPrimary, secondaryBetterDescription],
};
const deduped = deduplicateCrossSourceDataset(dataset);
assert.equal(deduped.events.length, 1, "semantic dedupe cardinality must remain unchanged");
assert.equal(deduped.counts.total, 1);
assert.equal(deduped.counts.events, 1);

const exhibitionA = event({
  id: "expo-a",
  source_id: "museum-source",
  title: "Primera exposición",
  primary_category: { id: "exposiciones", label: "Exposiciones" },
  categories: [{ id: "exposiciones", label: "Exposiciones" }],
  location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" },
  schedule: { start: "2026-08-01", end: "2026-09-01", occurrences: [] },
});
const exhibitionB = event({
  id: "expo-b",
  source_id: "museum-source",
  title: "Segunda exposición",
  primary_category: { id: "exposiciones", label: "Exposiciones" },
  categories: [{ id: "exposiciones", label: "Exposiciones" }],
  location: { venue: "Museo Palacio Rioja", city: "Viña del Mar" },
  schedule: { start: "2026-08-05", end: "2026-08-30", occurrences: [] },
});
assert.equal(areProbableDuplicateEvents(exhibitionA, exhibitionB), false, "same-source exhibitions are distinct semantic events");
const visualGroups = groupStandaloneExhibitions([exhibitionA, exhibitionB], { timezone: "America/Santiago" });
assert.equal(visualGroups.length, 1, "distinct semantic events may still share one visual group");
assert.equal(visualGroups[0].events.length, 2);

assert.match(orchestrator, /event-identity-core\.mjs/);
assert.match(orchestrator, /occurrence-identity-core\.mjs/);
assert.doesNotMatch(orchestrator, /RECURRENCE_TITLE_TOKENS|STRICT_START_TOLERANCE_MINUTES|function\s+titleCore|function\s+venueTokens/, "dedupe orchestrator must not own identity rules");
assert.match(eventIdentity, /occurrence-identity-core\.mjs/, "event identity may consume occurrence identity");
assert.doesNotMatch(eventIdentity, /exhibition-group-core/, "semantic identity must not depend on visual grouping");
assert.doesNotMatch(occurrenceIdentity, /event-identity-core|exhibition-group-core/, "occurrence identity must remain independent");
assert.doesNotMatch(visualGrouping, /event-identity-core|occurrence-identity-core|cross-source-deduplication/, "visual grouping must remain independent from semantic dedupe");

console.log("IDENTITY_OCCURRENCE_VISUAL_BOUNDARIES_OK");
