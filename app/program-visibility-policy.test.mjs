import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  applyProgramVisibilityPolicy,
  isProgramCovered,
  partitionPrograms,
  programReferenceTitle,
} from "./program-visibility-policy.js";

function event(overrides = {}) {
  return {
    id: "event-1",
    title: "Evento individual",
    event_type: "event",
    source_id: "centex",
    source_name: "CENTEX",
    location: { venue: "CENTEX", city: "Valparaíso" },
    schedule: { start: "2026-08-19T19:00:00-04:00", end: null },
    ...overrides,
  };
}

function program(overrides = {}) {
  return {
    id: "program-1",
    title: "Centex – Cartelera Agosto",
    event_type: "program",
    source_id: "valpocultura",
    source_name: "Valpo Cultura",
    organizer: "CENTEX",
    location: { venue: "CENTEX", city: "Valparaíso" },
    schedule: { start: "2026-08-01", end: "2026-08-31" },
    editorial: { covered_source_ids: ["centex"] },
    links: { official: "https://valpocultura.cl/evento/centex-cartelera-agosto/" },
    ...overrides,
  };
}

{
  const concrete = [event()];
  assert.equal(isProgramCovered(program(), concrete), true, "a fully covered program should be hidden from public presentation");
}

{
  const uncovered = program({ editorial: { covered_source_ids: ["centex", "another_source"] } });
  assert.equal(isProgramCovered(uncovered, [event()]), false, "partial coverage must keep the program as a secondary reference");
}

{
  const noCoverageMetadata = program({ editorial: {} });
  assert.equal(isProgramCovered(noCoverageMetadata, [event()]), false, "programs without coverage metadata remain available as references");
}

{
  const concrete = event();
  const coveredProgram = program();
  const uncoveredProgram = program({
    id: "program-2",
    title: "Valparaíso Profundo – Programación Agosto",
    location: { venue: "Valparaiso Profundo", city: "Valparaíso" },
    editorial: { covered_source_ids: ["valparaiso_profundo"] },
  });
  const result = partitionPrograms([coveredProgram, concrete, uncoveredProgram]);
  assert.deepEqual(result.publicEvents.map((item) => item.id), ["event-1"]);
  assert.deepEqual(result.hiddenPrograms.map((item) => item.id), ["program-1"]);
  assert.deepEqual(result.secondaryPrograms.map((item) => item.id), ["program-2"]);
}

{
  const dataset = {
    schema_version: "1.2.0",
    counts: { total: 3, events: 1, courses: 0, flexible_offers: 0, programs: 2 },
    events: [
      program(),
      event(),
      program({
        id: "program-2",
        title: "Valparaíso Profundo – Programación Agosto",
        location: { venue: "Valparaiso Profundo", city: "Valparaíso" },
        editorial: { covered_source_ids: ["valparaiso_profundo"] },
      }),
    ],
  };
  const result = applyProgramVisibilityPolicy(dataset);
  assert.equal(result.dataset.events.length, 1, "programs must not enter the primary event list");
  assert.equal(result.dataset.counts.total, 1, "primary public totals must exclude reference programs");
  assert.equal(result.dataset.counts.programs, 0);
  assert.equal(result.secondaryPrograms.length, 1, "only uncovered programs remain for the collapsed reference area");
}

{
  assert.equal(programReferenceTitle(program()), "CENTEX — programación de agosto");
  assert.equal(
    programReferenceTitle(program({
      title: "Valparaíso Profundo – Programación Agosto",
      location: { venue: "Valparaiso Profundo", city: "Valparaíso" },
    })),
    "Valparaíso Profundo — programación de agosto",
  );
}

{
  const webEnhancements = readFileSync(new URL("../assets/web-event-enhancements.js", import.meta.url), "utf8");
  assert.match(webEnhancements, /function setTextIfChanged\(/, "root WEB must avoid unconditional text-node rewrites");
  assert.match(webEnhancements, /new MutationObserver\(scheduleApply\)/, "root WEB observer must coalesce enhancement passes");
  assert.doesNotMatch(
    webEnhancements,
    /if \(date\) date\.textContent = formatSchedule/,
    "schedule enhancement must not retrigger its own MutationObserver indefinitely",
  );
  assert.doesNotMatch(
    webEnhancements,
    /if \(total\) total\.textContent/,
    "total enhancement must not retrigger its own MutationObserver indefinitely",
  );
}

{
  const pwaPolicy = readFileSync(new URL("./program-visibility-policy.js", import.meta.url), "utf8");
  assert.doesNotMatch(pwaPolicy, /new MutationObserver\(/, "program visibility must not depend on MutationObserver");
  assert.doesNotMatch(pwaPolicy, /(?:window|globalThis|target)\.fetch\s*=/, "program visibility must not monkey-patch fetch");
  assert.match(pwaPolicy, /export function renderProgramReferences\(/, "program references must render through an explicit core call");
}

console.log("PROGRAM_VISIBILITY_POLICY_OK");
