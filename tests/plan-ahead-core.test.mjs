import assert from "node:assert/strict";
import test from "node:test";

import { planAheadAction, planAheadCandidate, referenceNow, selectPlanAhead } from "../assets/plan-ahead-core.mjs";

const NOW = new Date("2026-08-17T12:00:00-04:00");

function event(overrides = {}) {
  return {
    id: "event-1",
    title: "Concierto futuro",
    event_type: "event",
    schedule: { start: "2026-09-06T20:00:00-03:00" },
    links: { official: "https://example.org/event", tickets: "https://example.org/tickets", registration: null },
    public_status: { cancelled: false, sold_out: false, registration_closed: false, registration_open: null },
    description: "Concierto con entradas a la venta.",
    registration_requirements: null,
    ...overrides,
  };
}

test("selects actionable events in the 2–8 week horizon", () => {
  const selected = selectPlanAhead([
    event(),
    event({ id: "too-soon", schedule: { start: "2026-08-25T20:00:00-04:00" } }),
    event({ id: "too-late", schedule: { start: "2026-10-20T20:00:00-03:00" } }),
  ], { now: NOW });

  assert.deepEqual(selected.map((candidate) => candidate.event.id), ["event-1"]);
  assert.equal(selected[0].action.kind, "tickets");
  assert.ok(selected[0].badges.includes("Entradas disponibles"));
});

test("supports registration-open status through the official page", () => {
  const candidate = planAheadCandidate(event({
    id: "registration",
    links: { official: "https://example.org/register", tickets: null, registration: null },
    public_status: { registration_open: true, registration_closed: false, cancelled: false, sold_out: false },
  }), { now: NOW });

  assert.ok(candidate);
  assert.equal(candidate.action.kind, "registration");
  assert.equal(candidate.action.url, "https://example.org/register");
  assert.equal(candidate.action.actionLabel, "Ver inscripción");
});

test("does not surface sold-out, cancelled, closed or non-actionable events", () => {
  const cases = [
    event({ id: "sold", public_status: { sold_out: true } }),
    event({ id: "cancelled", public_status: { cancelled: true } }),
    event({ id: "closed", links: { official: "https://example.org", tickets: null, registration: "https://example.org/register" }, public_status: { registration_closed: true } }),
    event({ id: "passive", links: { official: "https://example.org", tickets: null, registration: null }, public_status: {} }),
  ];
  assert.deepEqual(selectPlanAhead(cases, { now: NOW }), []);
});

test("marks limited capacity and prioritizes registration over ordinary ticket sales", () => {
  const registration = event({
    id: "registration",
    description: "Inscripción previa. Cupos limitados.",
    links: { official: "https://example.org", tickets: null, registration: "https://example.org/register" },
  });
  const tickets = event({ id: "tickets", schedule: { start: "2026-09-05T20:00:00-03:00" } });
  const selected = selectPlanAhead([tickets, registration], { now: NOW });

  assert.equal(selected[0].event.id, "registration");
  assert.ok(selected[0].badges.includes("Cupos limitados"));
});

test("recognizes registration, reservation, tickets and registration requirements", () => {
  assert.equal(planAheadAction(event({ links: { registration: "https://example.org/r", tickets: "https://example.org/t", official: "https://example.org" } })).kind, "registration");
  assert.equal(planAheadAction(event({ links: { official: "https://example.org", tickets: null, registration: null, reservation: "https://example.org/book" } })).kind, "reservation");
  assert.equal(planAheadAction(event()).kind, "tickets");
  assert.equal(planAheadAction(event({ links: { official: "https://example.org", tickets: null, registration: null }, registration_requirements: "Inscripción previa" })).kind, "requirements");
});

test("uses dataset generation time as the stable planning reference", () => {
  assert.equal(referenceNow({ generated_at: "2026-08-17T11:22:55-04:00" }).toISOString(), "2026-08-17T15:22:55.000Z");
});
