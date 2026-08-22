# Contract architecture — Stage D

Stage C established one canonical authority for each semantic business rule. Stage D applies the same rule to validation:

> **One product contract → one canonical test owner.**

A workflow may compose canonical owners, but it should not independently re-encode the same behavior with another set of literals, `grep` checks, duplicated fixtures, or parallel browser assertions.

## Contract layers

1. **Semantic** — pure business behavior: temporal classification/order, visibility decisions, schedules, category mapping, title normalization, venue identity, source evidence, identity/dedupe and image selection.
2. **Architecture** — ownership boundaries and integration invariants: which module is authoritative, shared runtime rules, third-city extensibility, startup composition.
3. **Browser** — observable user scenarios in a real browser. These tests assert rendered state and interactions, not the source-code spelling used to produce them.
4. **Release** — generated shell, cache/bundle coherence, protected production boundaries and production smoke.

The machine-readable ownership map is `tests/contract-topology.json`; `app/scripts/test_contract_topology.py` validates it. Executable semantic/architecture owners are invoked through `app/scripts/run_contracts.py`; browser owners are composed by `app/scripts/run_browser_scenarios.py`.

## Rules

- Every contract ID has exactly one owner.
- Stage C authority domains must have a semantic or architecture owner.
- Workflows execute canonical owners through runner profiles rather than duplicating their command lines.
- A browser contract belongs to at most one canonical browser scenario.
- An architecture test may assert a module boundary when the boundary itself is the contract; it should not freeze unrelated implementation details.
- Browser tests own user-visible behavior. Static tests should not duplicate a browser scenario by matching internal source literals.
- Release tests own generated/deployment integrity and may compose semantic, architecture and browser owners.
- Moving a canonical implementation should normally require updating one owner contract, not multiple unrelated workflow literals.

## Stage D sequence

### D1 — Contract topology — CLOSED

Created and validated the ownership map without runtime, dataset, editorial or PWA behavior changes.

### D2 — Canonical contract runner — CLOSED

`run_contracts.py` reads the topology and executes owners by ID/profile. The `shared-presentation`, `required-release` and `multi-city` profiles preserve canonical owners while removing duplicate generated-shell, multi-city UI, contextual-filter and startup-architecture executions.

### D3 — Scenario-oriented E2E — CURRENT

`run_browser_scenarios.py` composes browser contracts into observable user flows:

- `startup-city`: first paint, startup resilience/safe mode and Valparaíso → Gijón city switch.
- `filters-detail-media`: filters/date/visibility plus opening an event detail with canonical source and media.
- `exhibitions`: visual parity plus grouped-exhibition filter isolation.

The required release gate owns those scenario launches. `Multi-city pre-release` no longer launches browser tests. The service-worker cache-first startup contract remains a release/static invariant rather than being mislabeled as browser E2E.

There are no remaining declared temporary overlaps after D3.

### D4 — Release/production gate closure

Leave a simple final topology: fast semantic/architecture PR contracts, one required release/E2E gate, and post-merge production smoke. Replace stale implementation-history checks or version-specific notes with stable product/release invariants and move any remaining browser owner to the single required E2E gate.

## Current known overlaps

None declared. D4 validates the final gate roles and ensures browser execution is centralized without weakening production smoke or fast semantic/architecture coverage.
