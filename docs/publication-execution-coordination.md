# Exact Core publication execution ownership

This is coordination of the existing publisher/finalizer/certifier path, not a
new release producer or signature system. No jobs, schedules, credentials or
polling loops are added. Core's existing bounded certifier owns the deadline.

## Routes

- A trusted no-release decision retains its successful no-write outcome. The
  existing prior-base classifier and PR finalization authority are unchanged.
- A release push without PR authority is preliminary and **NOT_CERTIFIED**.
  This execution performs no Cloudflare mirror write, smoke or certification.
  It claims no Core identity and is not reclassified as no-release. GitHub's
  independently configured legacy Pages build may still advance public bytes
  after the push; those bytes remain pending certification. An unexpected
  direct push receives no authority or certificate through this route.
- An authenticated Core `repository_dispatch` must pass the unchanged detached
  Sigstore consumer. Its exact original receipt, lineage and signed bundle are
  carried through both jobs and the final semantic chain. It may claim the
  single canonical execution only if public main still equals its signed
  candidate. Existing PR release behavior is not subjected to that Core check.
- Another dispatch with the identical binding delegates to the demonstrated
  canonical execution. It does not retry a failed owner or rewrite the mirror.
  Successful reuse additionally requires that owner's exact durable certificate.
  A queued/pending/requested/waiting callback with no started job/step has not claimed anything and does
  not block the running owner. In-progress or failed unproven executions block.
  None of these states extends Core's existing bounded certification deadline.

## Public index, private authority

The existing `sync-cloudflare` job emits one `CORE_PUBLICATION_EXECUTION_V1`
Checks notice after successful cryptographic verification and before deployment.
This **index is not a signature**. Core authenticates the original private
artifact itself; the public index binds the demonstrated use of those bytes to
the exact Web run, attempt, GitHub Actions check and successful verification and
emission steps. Core does not need a cross-repository artifact-download token.
The full transported evidence remains in the Web artifact for audit.

The closed binding includes Core SHA, intent, publisher/finalizer and attempts,
acquisitions, fence hash, public/parent SHA, release identity, and exact hashes of
lineage, receipt, release bundle and signed bundle. The signer remains the Core
finalizer; the diagnostic workflow is not accepted as production authority.

GitHub metadata must agree on repository, workflow path/id, run/attempt, job,
check and GitHub Actions app. The fixed critical-code blob set in both the
checked-out candidate and the executing workflow must match the signed public
parent. A late callback may execute at a different Web workflow
SHA only when those exact blobs remain identical. Identity is never inferred
from author, commit message, ancestry, API order or a green conclusion.

Canonical and delegated indices form one explicit root graph. Two roots,
crossed references, changed attempts, missing evidence or failed authority
checks block. No `first`, `latest` or fallback-green selection is permitted.
Public API reads are paginated, bounded and fail closed on access errors.

## Certification and replay

The canonical visual certificate retains the entire verified execution index.
History rejects Core/PR downgrades and conflicting claims at the same public
SHA/release. The watchdog checks exact binding/owner in the durable archive and
compares the downloaded visual attestation with its original recorded hash and
execution index. It never substitutes the dispatch workflow SHA for the signed
public SHA. A delegated watchdog confirms reuse, not a second certification.

This change supports duplicate **dispatch deliveries** with distinct run IDs.
A manual Web rerun (`run_attempt > 1`) is deliberately rejected before claiming
or writing: `UNSUPPORTED_RERUN_REQUIRES_ORIGINAL_EXECUTION`. Reconstructing every
historical attempt is not silently approximated. Signed publisher/finalizer
attempts are still validated as supplied; they are not limited to attempt one.

Local fixtures test routing, public metadata, history and byte/identity
contradictions; they do not claim a new remote signature or publication. The
previous real private-attestation diagnostic and final-receipt editorial replay
remain separate evidence. The compatible Web consumer must be integrated before
the Core producer, and old publishers/finalizers must drain before activation.

Actions impact is additional metadata reads, hashes, verification and retained
evidence inside existing jobs. No measured cost or time saving is claimed.

The transport relies on GitHub's official public
[Checks annotations API](https://docs.github.com/en/rest/checks/runs#list-check-run-annotations).
The [artifact download API](https://docs.github.com/en/rest/actions/artifacts#download-an-artifact)
has a different permission contract; this design does not assume private Core's
repository-scoped token can download Web artifact ZIPs.
