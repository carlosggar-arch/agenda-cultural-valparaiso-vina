# Production certification SLA

## Purpose

Production certification is a correctness boundary, not a long-running observation loop. A release must be certified against the exact SHA that triggered publication and must either produce a durable certification quickly or fail closed as `PRODUCTION_UNCERTIFIED`.

## Canonical flow

1. `sync-cloudflare` receives immutable `CANDIDATE_SHA = github.sha`.
2. `cloudflare-preview` merges that exact candidate; it never merges a later `origin/main` implicitly.
3. GitHub Pages and Cloudflare are polled concurrently by `app/scripts/deployment_readiness.py`.
4. The shared deployment-readiness wait is bounded to 90 seconds.
5. After readiness, production verification performs only a one-shot byte assertion; it never starts another deployment wait.
6. Independent post-deployment probes run concurrently:
   - admin environment separation + structural series contracts;
   - browser/cold-load/image verification;
   - warm PWA reopen;
   - exact WEB↔cached-PWA presentation parity.
7. The existing attestation and source-to-production chain are built only if all probe groups succeed.
8. `publish.yml` remains the unique writer of `state/production-certifications`.
9. The persisted attestation must contain the original `CANDIDATE_SHA`; a different head is rejected.

## Time budget

- deployment synchronization job: hard timeout 3 minutes;
- shared network readiness wait: maximum 90 seconds;
- visual/functional certification job: hard timeout 7 minutes;
- normal target for merge → durable certification: 3–6 minutes;
- architectural fail-closed ceiling before the publication workflow terminates: approximately 10 minutes, excluding the non-certifying PR-refresh follow-up.

The time budget is enforced by `app/scripts/test_production_certification_latency_contract.py` in PR CI. Reintroducing the legacy 28-minute timeout, `git reset --hard origin/main`, a second wait loop, or serial independent probes is a contract violation.

## Safety properties retained

This optimization does not remove production checks. It changes orchestration only: immutable candidate selection, one bounded deployment wait, parallel independent verification, the same release attestation, the same exact source-to-production chain, immutable certification history, and the read-only certification watchdog.
