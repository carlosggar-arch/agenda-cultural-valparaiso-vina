# GitHub Actions architecture and rollback map

This document identifies the CI cost controls introduced in August 2026 and the files that own them. Each component can be reviewed or reverted independently through the PR that introduced it.

## Ownership map

| Concern | Owner | Safety invariant |
| --- | --- | --- |
| Domain selection | `tests/ci-domain-map.json` | Every product-relevant tracked path has exactly one first-match domain. |
| Contract planner | `app/scripts/run_impacted_contracts.py` | Shared, unknown, and critical WEB–APP paths execute `pr-fast-all`. |
| Selection regression | `app/scripts/test_ci_domain_selection.py` | Fails when a relevant tracked path is unowned or a critical path is narrowed. |
| Changed source tests | `app/scripts/run_changed_source_tests.py` | Audit tests run in PR validation; live probes remain scheduled/manual. |
| Dependency cache | `requirements-ci.txt` and `setup-python` cache settings | Cache keys derive from the pinned dependency file; no generated or untrusted cache key is used. |
| Publication | `.github/workflows/publish.yml` | `sync-cloudflare` and `production-smoke` remain separate jobs, with smoke depending on sync. |
| Workflow invariants | `app/scripts/test_ci_economy.py` | Trigger count, job separation, stable release context, and action generations are enforced. |

## Trigger model

- `Scheduled adaptive source audit` runs only weekly or manually. Its deterministic audit and Balmaceda transport tests are selected by `Changed source validation` on pull requests.
- `PR fast contracts` always runs structural guards and then uses the domain map for product contracts.
- Shared, critical, or unknown product changes deliberately spend the full fast-contract budget.
- The release browser gate remains separate and keeps the stable `release-guard` check name.

## Safe rollback

Prefer reverting the merge commit for the CI architecture PR. If a partial rollback is required, revert the selector, map, and selection regression together; reverting only one would remove the total-coverage guarantee. Do not combine publication-job rollback with domain-selection rollback unless both are intentionally being changed.

Branch deletion evidence is recorded separately in `docs/BRANCH_CLEANUP_2026-08-23.md`; deleted branches can be recreated from the exact commit listed there.
