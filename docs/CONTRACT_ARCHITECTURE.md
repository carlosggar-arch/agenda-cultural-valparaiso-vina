# Contract architecture — Stage D

Stage C established one canonical authority for each semantic business rule. Stage D applies the same rule to validation:

> **One product contract → one canonical test owner.**

A workflow may compose canonical owners, but it should not independently re-encode the same behavior with another set of literals, `grep` checks, duplicated fixtures, or parallel browser assertions.

## Contract layers

1. **Semantic** — pure business behavior: temporal classification/order, visibility decisions, schedules, category mapping, title normalization, venue identity, source evidence, identity/dedupe and image selection.
2. **Architecture** — ownership boundaries and integration invariants: which module is authoritative, shared runtime rules, third-city extensibility, startup composition.
3. **Browser** — observable user scenarios in a real browser. These tests should assert rendered state and interactions, not the source-code spelling used to produce them.
4. **Release** — generated shell, cache/bundle coherence, protected production boundaries and production smoke.

The machine-readable ownership map is `tests/contract-topology.json`; `app/scripts/test_contract_topology.py` validates it. Executable canonical owners are invoked through `app/scripts/run_contracts.py`, by contract ID or by a topology-defined profile.

## Rules

- Every contract ID has exactly one owner.
- Stage C authority domains must have a semantic or architecture owner.
- Workflows execute canonical owners through runner profiles rather than duplicating their command lines.
- An architecture test may assert a module boundary when the boundary itself is the contract; it should not freeze unrelated implementation details.
- Browser tests own user-visible behavior. Static tests should not duplicate a browser scenario by matching internal source literals.
- Release tests own generated/deployment integrity and may compose semantic, architecture and browser owners.
- Temporary duplication must be declared under `temporary_overlaps` with a target Stage D sub-stage for removal.
- Moving a canonical implementation should normally require updating one owner contract, not multiple unrelated workflow literals.

## Stage D sequence

### D1 — Contract topology — CLOSED

Created and validated the ownership map without runtime, dataset, editorial or PWA behavior changes.

### D2 — Canonical contract runner — CURRENT

`run_contracts.py` reads the D1 topology and executes owners by ID/profile. The `shared-presentation`, `required-release` and `multi-city` profiles preserve the existing canonical owners while removing duplicate execution of generated-shell, multi-city UI and contextual-filter contracts. A stray duplicate startup architecture execution in the shared-presentation workflow was also removed.

After D2, the only declared temporary overlap is `browser.first-render`, intentionally retained until D3.

### D3 — Scenario-oriented E2E

Consolidate real-browser validation around user scenarios (startup/city switch, filters/date/visibility, exhibitions, event detail/media, installed/cache behavior). A scenario gets one browser owner and may be invoked by the required release gate; duplicate launches are removed.

### D4 — Release/production gate closure

Leave a simple final topology: fast semantic/architecture PR contracts, one required release/E2E gate, and post-merge production smoke. Replace stale implementation-history checks or version-specific notes with stable product/release invariants.

## Current known overlaps

D2 retires all overlaps scheduled for D2. `browser.first-render` remains the sole temporary overlap and is scheduled for removal in D3. No runtime or production-data behavior is changed by this consolidation.
