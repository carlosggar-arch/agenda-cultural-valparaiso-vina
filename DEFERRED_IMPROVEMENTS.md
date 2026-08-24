# Deferred Improvements

This document records improvements that are considered useful but are **not required to regard the current architecture as complete or production-safe**. Items belong here when implementing them immediately would reopen a stable subsystem without a corresponding correctness need.

## Production certification follow-ups

**Baseline already complete:** PR #456 established the canonical fast deterministic certification architecture: immutable `CANDIDATE_SHA`, one bounded shared deployment-readiness wait, parallel independent production probes, a unique certification writer, exact source-to-production lineage, immutable certification history, and fail-closed watchdog protection. Its first production certification completed in about 1m50s. The items below must preserve those invariants.

### 1. Per-stage certification timing telemetry

**Priority:** High  
**Status:** Deferred optimization  
**Why defer:** The certification SLA is already met; this improves observability rather than correctness.

Persist structured durations for the main certification phases, at least:

- candidate-to-Cloudflare synchronization;
- GitHub Pages readiness;
- Cloudflare readiness;
- admin + series probes;
- browser/cold-load/image probes;
- warm PWA reopen;
- WEB↔PWA parity;
- attestation and immutable-history persistence;
- total merge-to-certification duration.

The timings should be attached to the durable certification evidence or an append-only companion record so regressions can be detected without parsing workflow logs.

**Acceptance criteria:** timings are machine-readable; do not alter the pass/fail semantics of certification; no new writer is introduced; the existing immutable `CANDIDATE_SHA` remains authoritative.

### 2. Supersession/coalescing of equivalent certification candidates

**Priority:** Medium  
**Status:** Deferred efficiency improvement  
**Why defer:** Useful only when multiple equivalent PRs are merged in quick succession; current correctness is unaffected.

When several queued candidates have the same `release_fingerprint` and no runtime/data change requires distinct certification, allow older not-yet-started candidates to be recorded as `superseded_before_certification` and certify the newest equivalent candidate instead of running the full production suite repeatedly.

This must never erase provenance. Every merged SHA must remain traceable, including the SHA that superseded it and the reason equivalence was considered safe.

**Acceptance criteria:** no already-started certification changes candidate SHA; equivalence is based on deterministic release/runtime evidence, not only release number; superseded candidates remain durably auditable; the newest candidate still receives full production certification.

### 3. Selective retry of failed independent production probes

**Priority:** Medium  
**Status:** Deferred resilience optimization  
**Why defer:** The current fail-closed full run is correct; this would reduce recovery cost for isolated transient failures.

Permit retrying only the failed independent probe group—such as browser/images, warm PWA, admin+series, or WEB↔PWA parity—while keeping the same immutable `CANDIDATE_SHA` and the already-valid evidence from successful groups.

A certificate must still be emitted only after every required probe has passed for that exact candidate.

**Acceptance criteria:** retries cannot switch to a newer `main`; successful evidence is bound cryptographically or structurally to the same candidate/run lineage; stale evidence expires or is invalidated when relevant inputs change; certification remains fail-closed.

### 4. Certification performance history in `/admin-staging`

**Priority:** Medium-Low  
**Status:** Deferred observability/UI improvement  
**Why defer:** Operationally useful but not required for publication correctness.

Expose a compact read-only view of recent certification performance, for example:

`Last certification: 1m50s · readiness: 12s · browser: 58s · PWA: 31s`

Also consider rolling median/p95 for recent releases so degradation is visible before the hard SLA is exceeded.

This UI must consume canonical durable timing evidence rather than workflow-log scraping and must remain strictly read-only.

**Acceptance criteria:** production and preview remain clearly separated; no write capability is added to admin staging; missing telemetry is shown as unavailable rather than inferred; historical metrics do not affect certification state.

## Guardrail for future implementation

These deferred items are optimizations around the certified architecture, **not permission to redesign its invariants**. Any future implementation must preserve:

- immutable certification candidate SHA;
- one bounded deployment-readiness phase;
- parallel independent probes where safe;
- one canonical certification writer;
- exact source → finalizer → `main` → Cloudflare → production provenance;
- permanent fail-closed certification evidence and watchdog behavior;
- the current certification latency contract unless a stricter SLA replaces it.
