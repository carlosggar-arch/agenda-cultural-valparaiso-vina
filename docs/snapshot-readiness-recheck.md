# Bounded readiness confirmation for an already-written snapshot

## Observed failure and limited fix

Web `56f32a21f42709514fc2a6459b2ae3a6428dae8f` was written by Core
`dcc8ac9bf344eb624727281c6c15ef75ad7849da`, publisher `34712847317/1`,
finalizer `34714618908/1`. Its Web verification `34714687563/1` failed
at the second network probe in `assert_all_ready`, around 35 seconds into
the original 90-second wait. The first probe in that iteration had passed.
The second reported a Cloudflare mismatch for `../agenda_web.json` and
exited immediately instead of remaining in the bounded wait.

The regression uses explicit synthetic probe results, not fabricated
historical responses. The unchanged verifier fails the ready / mismatch /
ready sequence; the corrected waiter requires a successful confirmation
within the original retry loop. A persistent mismatch still times out.
Only the typed readiness failure is retried: shell failures remain fatal,
and standalone `--assert-ready` still has one probe and no retries. Neither
the 90-second budget nor the candidate, signature or identity guards change.
Mismatch diagnostics now retain expected and observed SHA-256 digests.

The historical response body, digest, headers and request UUID were not
archived. The expected dataset was 1,025,189 bytes, SHA-256
`57d9f8897715e9764268e006571afcc8f6fa97d67b9a559950f18e7a40816470`.
The path represents `https://vivamos.pages.dev/agenda_web.json`; the actual
fetcher concatenates `/app/../agenda_web.json?smoke=<uuid>`. Both literal and
normalized paths, and both production origins, matched the exact snapshot
in the later read-only observation. This does not prove historical cache
behavior, a propagation cause, or convergence within the original budget.

## Not a route to certify the old run

This patch is local preparation, not a deployment or certification.
The existing routing deliberately rejects `run_attempt != 1` with
`CORE_EXECUTION_UNSUPPORTED_RERUN_REQUIRES_ORIGINAL_EXECUTION`. Its index,
visual history, watchdog and Core consumer require the exact owner/attempt.
A duplicate callback delegates to that failed owner rather than redeploying.
Furthermore Core's certifier has no callback triggered by Web completion.
Removing one guard would not produce a valid verification chain.

A future reviewed route must separate the original signed writer identity
and public snapshot from a new verifier-code SHA and run/attempt. It must
retain the original receipt, Sigstore bundle, failure and artifact IDs;
perform the omitted visual smoke; and link a new immutable verification to
the original owner before official watchdog/certification/promotion.
Neither historical indexes nor the signed workflow authority may be
reinterpreted. The new verifier needs independently approved code identity,
not a self-declared trusted JSON field or a retroactive finalizer signature.
Cross-repository orchestration and its limited dispatch capability are not
declared today and require a separately reviewed implementation. No such
workflow, input, permission or authority exception is introduced here.

## Local validation

- Six new behavior regressions, executed by the existing mandatory latency
  contract: changing confirmation, persistent mismatch, digest evidence,
  missing origin, one-shot assertion and fatal shell error.
- Existing PR-fast topology/writer/finalization/history/watchdog contracts;
  the 22-contract `pr-fast-all` profile selected for these script changes;
  release diagnostics, production-smoke structural contract, Node tests and
  generated-module checks passed locally.
- No workflow, schedule, dataset, release, receipt, durable state, runtime
  presentation or acquisition code changes. Impact is product=true,
  generated=false, release=false under the existing classifier.
- Web has no `scripts/validate_change.ps1`; Core's script hard-codes the Core
  project and is not a Web gate. Web's actual applicable gates above were
  used. No live E2E or remote verification is claimed by these local tests.

The single conditional verification authorization was not consumed. The
target remains published but uncertified, with its intent still active.
The editorial dispatch was already consumed and must not be reused.
