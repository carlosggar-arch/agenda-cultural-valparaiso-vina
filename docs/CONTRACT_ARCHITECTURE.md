# Contract architecture — Stage D

Stage C established one canonical authority for each semantic business rule. Stage D applies the same rule to validation:

> **One product contract → one canonical test owner.**

A workflow may compose canonical owners, but it should not independently re-encode the same behavior with another set of literals, `grep` checks, duplicated fixtures, or parallel browser assertions.

## Contract layers

1. **Semantic** — pure business behavior: temporal classification/order, editorial tie-breaks, content-kind presentation, visibility decisions, schedules, category mapping, title normalization, venue identity, source evidence, identity/dedupe and image selection.
2. **Architecture** — ownership boundaries and integration invariants: which module is authoritative, shared runtime rules, third-city extensibility, startup composition and read-only editorial quality auditing.
3. **Browser** — observable user scenarios in a real browser. These tests assert rendered state and interactions, not the source-code spelling used to produce them.
4. **Release** — generated shell, cache/bundle coherence, protected production boundaries and production smoke.

The machine-readable ownership map is `tests/contract-topology.json`; `app/scripts/test_contract_topology.py` validates it. Executable semantic/architecture/release owners are invoked through `app/scripts/run_contracts.py`, including declarative `runner_args`; browser owners are composed by `app/scripts/run_browser_scenarios.py`.

## Final rules

- Every contract ID has exactly one owner.
- Stage C authority domains have semantic or architecture owners.
- Workflows execute canonical owners through runner profiles rather than duplicating their commands.
- Every browser contract belongs to exactly one canonical browser scenario.
- Every browser contract is composed by `Required release guard`; fast PR workflows do not launch browsers.
- Architecture tests assert ownership boundaries rather than historical implementation spelling.
- Browser tests assert user-visible state and interactions rather than source literals.
- Local release/shell behavior is checked before merge; network/deployment behavior is checked after merge against public `main`.
- `temporary_overlaps` is empty; Stage D has no accepted validation overlap debt.

## Shared editorial structure

The agenda uses the same editorial architecture for every city registered in `app/cities.json`:

- `temporal-priority-core.mjs` remains the authority for temporal bucket and `content_kind`; no city may override urgency semantics.
- `editorial-priority-core.mjs` provides a small, factual and explainable tie-break based on source quality, information completeness, one-day specificity and explicit singular-event flags. It is evaluated only after temporal semantics are tied.
- `content-kind-presentation.mjs` translates the canonical `content_kind` into one shared public meaning such as **Fecha concreta**, **En curso**, **Recurrente** or **Disponible**. Renderers and cities do not maintain parallel labels.
- `audit_editorial_quality.py` audits every registered public dataset for structural/editorial anomalies and produces a read-only report. The audit never publishes or mutates public data; public writer ownership remains outside this repository workflow.

These contracts are deliberately registry-driven. Adding another city through `app/cities.json` automatically brings its public dataset under the same editorial audit and the same runtime semantics without adding city-specific ranking, badge or audit code.

## Stage D sequence

### D1 — Contract topology — CLOSED

Created and validated the ownership map without runtime, dataset, editorial or PWA behavior changes.

### D2 — Canonical contract runner — CLOSED

`run_contracts.py` reads the topology and executes owners by ID/profile. The `shared-presentation`, `required-release` and `multi-city` profiles preserve canonical owners while removing duplicate generated-shell, multi-city UI, contextual-filter and startup-architecture executions.

### D3 — Scenario-oriented E2E — CLOSED

`run_browser_scenarios.py` consolidated real-browser validation into observable user flows:

- `startup-city`: first paint, startup resilience/safe mode and Valparaíso → Gijón city switch.
- `filters-detail-media`: filters/date/visibility plus event detail, canonical source evidence and media.
- `exhibitions`: visual parity plus grouped-exhibition filter isolation.

The required release gate became the browser scenario compositor; `Multi-city pre-release` stopped launching browsers. Historical `dump-dom` runtime probing was replaced by deterministic Selenium interaction.

### D4 — Release/production gate closure — CLOSED

D4 closes the final roles without changing product runtime or data:

- `temporal-fast` contains only `semantic.temporal-priority` and `semantic.agenda-order`.
- `browser.temporal-priority` moves into the canonical `temporal-order` browser scenario under `Required release guard`.
- the generic contract runner honors declarative `runner_args`, so the local PWA smoke is a normal canonical release contract rather than a YAML special case.
- local public-presentation, PWA-shell and production-smoke contracts are composed before merge by `Required release guard`.
- `Production PWA smoke` has no PR trigger; push-to-`main` (or manual rerun) aligns to latest public `main` and then verifies GitHub Pages/Cloudflare byte parity, cold loads and warm reopen.
- stale version-history assertions were removed in favor of stable release/gate invariants.

## Final gate topology

**Fast PR contracts** → semantic and architecture checks such as shared presentation, taxonomy, grouping and `temporal-fast`.

**Required release guard** → local release integrity + all canonical browser scenarios (`startup-city`, `filters-detail-media`, `exhibitions`, `temporal-order`).

**Post-merge production smoke** → actual public deployments on GitHub Pages and Cloudflare, including byte parity, both-city cold load and Valparaíso mobile warm reopen.

## Current known overlaps

None. The topology declares no temporary overlap and D4's structural tests reject any browser owner outside the single required E2E composer.