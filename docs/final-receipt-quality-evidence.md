# Private quality decisions survive finalizer reapplication

Companion to Core `codex/fix-final-receipt-funnel-accounting`, based on the failed
publisher `34583076464/1` and finalizer `34586222872/1`. Web base is
`e989befcf3ea879424ac9bb39956256e7acbbf8c`; no productive dataset is changed.

An intermediate corrected local finalization produced 329 events and a
valid canonical receipt. Reapplying its deterministic layers yielded the same
dataset and zero recoveries, but the next quality reports describe **this**
pass, so they no longer contain earlier quarantine/expiration decisions. The
receipt must not confuse a newly empty diagnostic report with lost evidence.

The guard now appends `candidate_quality_dispositions` to its existing private
transformation ledger when it actually transforms an input. Each envelope
contains the exact before event, its canonical hash and binding, evaluation
date, original decision and transformation/destination. Existing records are
preserved, not reconstructed from later reports. Crossed inputs, conflicting
decisions, duplicate envelopes and reinsertion are rejected.

This field is deliberately separate from `receipts`, whose protected-baseline
contract remains unchanged. Candidate-only exclusions cannot become baseline
loss authorizations. The companion Core consumer binds the decision back to the
immutable handoff, independently validates expiration and temporal obligations,
and preserves the original accepted universe. Quarantine and expiration are
never counted as publication. Diagnostic reports still describe the current
guard pass.

## Validation and compatibility

The new standard-library tests are included in the existing content-quality
guard test entrypoint, therefore in the official `pr-fast-all` selection. Local
classification of the accumulated product paths is `product=true`,
`generated=false`, `release=false`. All 12 topology commands, 22 fast contracts,
presentation checks, generated-runtime checks and compilation passed before the
coordinated final replay. No new dependencies or release artifacts are needed.

Five legacy transformation-ledger unit expectations also fail against the
exact base file blobs (malformed `single`/date-only or contradictory-end fixtures
expect temporal merges now forbidden by the integrated contract). They are
recorded, not counted as passing and not changed by this repair.

Integration order for review: **Core consumer first, then Web producer**.
Core new + Web old rejects a fresh quarantine whose accepted event ID is still
present. The old ledger's absent append-only proof never authorizes a baseline
restoration or silently publishes the quarantined event. Web new + Core old
does not fix the original mandatory expiration accounting failure. Neither
combination permits a manual bypass, publication dispatch or loss of checks.
Any PR must remain draft; this document authorizes no integration or publication.

The full offline replay, original hashes, per-observation terminal table and
final validation results are recorded in the companion Core document
`docs/final-receipt-funnel-accounting-validation.md`. Regenerated receipts are
local tests referencing historical inputs, not receipts from a remote run.

## Complete disposition transitions

Full disposition retention exposes two original quarantines that completeness
recovery reinserted after dropping their rejection-triggering fields. PUCV's
accepted baseline and capture contain 11 Sep at 12:00, but the recovered row has
only a date. Quarantining the accepted baseline would erase that verified
function. Fonck's recovered row still has no public-event evidence after its
review veto disappears. Core's companion now restores PUCV only from its exact
accepted baseline and own reprojected capture, retaining the original quarantine
as superseded evidence. It also preserves Fonck's upstream review fields so this
normal guard emits the real quarantine and per-observation disposition.

These changes do not broaden editorial policy. The complete replay must pass
both mandatory final receipts and retain all 318 accepted-candidate obligations
before the conditional push/draft PR authorization is exercised. The companion
Core document records the final sequence and any remaining limits.

The final `fixed-replay-07` now passes both real mandatory publication-receipt
checks offline, preserving all 318 handoff obligations and the 38 recovery
parents (28 retained, 10 quarantined). The second pass adds no recovery and
keeps dataset, ledger, terminal destinations and full funnel identical. WEB/APP
bytes match and Gijón's dataset and specific surfaces are unchanged. The original
code still reproduces the exact mandatory failure; none of these local results
is a remote publication or attestation. The companion Core document records
the final hashes, validated function restorations, inherited test limitations
and missing old HTML clock evidence. Both proposed PRs remain draft.
