# Verify an already-written Core publication

This mode does not create or deploy a candidate. It preserves the historical
Core signature, receipt, release and canonical Web owner. A new explicit
verification run is recorded separately; the original failures remain failures.
The existing rejection of publication reruns is unchanged.

## Why this is a separate execution

The first readiness probe of publication `56f32a21f42709514fc2a6459b2ae3a6428dae8f`
passed and its consecutive confirmation failed. Previously that second
confirmation escaped the bounded wait. Commit
`3fef8360f3b461016235ec33dd3baba2965056f1` corrects that control-flow defect without
relaxing byte comparisons. Later GETs matched both origins, but no response body
or digest was archived for the failed request; a CDN/cache cause is not proven.
The skipped visual probes still have to run. A matching GET is not certification.

The target preserves Core producer `dcc8ac9bf344eb624727281c6c15ef75ad7849da`,
publisher `34712847317/1`, finalizer `34714618908/1`, original Web execution
`34714687563/1`, and intent
`48a980e4daf3bbf17b2bb647bcad3cd6bf2e067cb6b505705814be7fad8d011c`.
Core certification `34714696322/1` and watchdog `34714745789/1` are historical
failures, not evidence of the new verification.

## Entry, unchanged data, and authority

The existing `publish.yml` accepts three optional inputs together:
`snapshot_public_sha`, `original_run_id`, `original_run_attempt`. With any one
present, the ordinary deployment path is disabled; incomplete inputs fail.
All absent preserve existing push/PR/publication behavior. The new mode requires
a new `workflow_dispatch` run, attempt 1, never the original run or its rerun.
There are no new schedules or automatic publishers.

The verifier and data are separate checkouts. The data checkout retains the
original Git HEAD. Only reviewed Python verifier files are overlaid, byte-checked
against the executing verifier commit before and after every sequence. New
untracked Python helpers and symlinks are checked too. The executing GitHub SHA
is never overridden with the publication SHA. Moving main, changed data/media, a different
attempt, expired/missing/ambiguous artifacts or changed signature bytes block.

When the public runtime has advanced after the immutable data publication, the
proof uses an explicit `historical-data-current-runtime-composition`. It binds
both full Git trees, both release identities, the exact changed-path set and the
Git blobs of the Valparaíso/Gijón datasets, source catalog/registry, three
quality reports and venue registry. Runtime-only code and generated release
metadata may differ; data, diagnostics, registries and media may not. The
historical release remains a failed historical deployment. All current
readiness, byte, browser, warm-start and WEB/APP probes run against the later
runtime/release, and the new attestation is archived under that runtime identity
while embedding the original signed Core execution.

The original artifact is resolved by run/attempt-qualified name, time window,
GitHub artifact ID and SHA-256 of the downloaded ZIP. Safe extraction preserves
the original ZIP and metadata. The private Sigstore verifier authenticates the
original bytes and finalizer identity again; it does not create a new signature.
The original canonical index is checked against historical GitHub Actions
run/job/check/notice metadata and its original code hashes.

A typed `snapshot_verification` proof identifies the later run and its whole
Git tree plus critical verifier blobs. Core independently approves that tree in
its versioned policy; the proof cannot approve itself. The watchdog validates
the new run, all required jobs, the complete immutable history, original private
signature again, and the exact archived attestation hash. It emits its own
run/attempt-bound proof. No skipped legacy synchronization job is called green.

GitHub annotations carry only a compact run/attempt-bound index and the SHA-256
of the proof. The full proof remains in the run-qualified
`snapshot-verification-<run>-<attempt>` artifact. The watchdog downloads that
exact artifact and requires its bytes to match the annotation digest before it
uses the proof. This avoids annotation truncation without moving authority into
an unauthenticated message or accepting a proof from another run.

A verification-only merge is not falsely presented as a deployed runtime
commit. If that merge is not an ancestor of `cloudflare-preview`, the chain
accepts only a complete Git diff confined to the same non-public verifier,
workflow, test and documentation paths checked before the probes. The chain
records that relation and the exact changed-path set. Any dataset, generated
release, runtime, page or asset difference still blocks.

Likewise, the current release is validated at the commit that last changed its
canonical provenance, not by pretending a later verification-only commit was
the release finalizer. That release owner must be an ancestor of the approved
verifier tree, and every intervening path must be non-public verification
machinery. The certificate records both identities and the intervening paths.

## Complete route and sole writers

1. `verify-snapshot`: original signature, original execution, immutable data and
   the exact historical/current composition.
2. `snapshot-production-smoke`: historical lineage checks followed by current
   runtime/local checks, bounded origin
   readiness, admin and series checks, full browser/cold-load/city-roundtrip/
   official-image checks, warm PWA, exact WEB/APP parity, network revalidation,
   source-to-production chain, then immutable Web certification history.
   The historical release check executes inside the immutable historical
   checkout and emits a structured, content-addressed result. The current
   runtime chain consumes that result while validating the current release in
   the current checkout; it never evaluates historical provenance against the
   later runtime metadata.
3. Existing watchdog: validates that exact result, then a separate callback job
   requests Core's existing `certify-publication-post-finalizer.yml` with the
   original finalizer plus the new verification and watchdog run/attempt pairs.
4. Core independently validates all authority and state bindings, then uses its
   existing certification persistence and CAS promotion. Only the exact
   published intent may become certified; other/deferred city records survive.

Only `publish.yml` writes `state/production-certifications`, via normal
fast-forward push. This mode does not synchronize Cloudflare or write Web main.
If both origins no longer serve the exact approved runtime over the preserved
data, it blocks rather than
silently deploying something else. There is no publisher/finalizer/recovery
dispatch here. The watchdog remains contents-read-only and never waits for
Core; Core can wait for the callback's watchdog run to become terminal without
a dependency cycle. All new artifacts have explicit 30-day retention and
run/attempt-qualified names.

## Integration and remaining operator prerequisite

This is local implementation, not an executed verification. Integrate the Web
verifier and the independently reviewed Core consumer/policy before invoking
the new mode. The Web tree approved in Core must equal both the verification
and watchdog execution trees. A squash may change commit identity, not tree;
any changed tree requires fresh policy review. Do not combine an editorial
dataset change with this verification-only integration.

The automatic callback needs a dedicated GitHub App installed on Core with
Actions write (plus GitHub's inherent metadata access), no contents write.
Web needs `CORE_CERTIFICATION_APP_ID` and
`CORE_CERTIFICATION_APP_PRIVATE_KEY`. No credentials are created, inspected or
configured by this change, and there is no fallback to publisher/writer keys.
Actions write is repository-wide, not restricted by GitHub to one workflow;
the reviewed callback code restricts its use to the certifier. Provisioning and
review of this capability remain an explicit prerequisite before any remote
attempt. Missing credentials fail closed, including the watchdog run. A
separate manual-only authentication diagnostic may dispatch only Core's bounded
private-attestation diagnostic with a run-bound nonce. It neither exercises nor
consumes the snapshot-verification attempt and cannot write Web or durable Core
state.

The existing trusted-impact/finalization contract remains intact. This diff
changes verifier scripts and workflows, not runtime/data or the protected PR
classification/finalization implementation: its expected impact is
`product=true, generated=false, release=false`, to be recalculated on the final
accumulated diff. An independently demonstrated no-release needs neither a
handoff nor a release commit. This code cannot grant itself trusted validation;
any later addition of protected machinery must follow the existing manual
review boundary, not synthesize evidence or reclassify files.

After integration, unchanged references, available original artifacts,
compatible idle operations, and callback credentials have been verified, the
single reserved verification would use:

```powershell
gh workflow run publish.yml --repo carlosggar-arch/agenda-cultural-valparaiso-vina --ref main -f snapshot_public_sha=56f32a21f42709514fc2a6459b2ae3a6428dae8f -f original_run_id=34714687563 -f original_run_attempt=1
```

Do not execute it as part of local tests. It is not the consumed editorial
dispatch. A failure stops the chain; no fallback mechanism or second attempt
is implied. Local API models/probe fixtures are labelled tests and cannot
certify production or claim that the missed visual smoke has now passed.
