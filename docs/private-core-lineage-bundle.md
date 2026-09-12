# Detached lineage for a private Core repository

## Scope and base

This consumer is prepared on `codex/private-publication-attestation`, based on
Web `1be7a53a32bb60af51ce85982a68d5a39a361c8f` (the preserved #518 repair).
It changes authentication transport, not editorial data, receipt accounting,
quarantine, occurrence preservation, release identity or publication authority.
It does not establish that this code has been merged, deployed or certified.

## Authentication contract

`app/scripts/verify_core_publication_bundle.py` is the common consumer for both
Web deployment entry points and the new Core writer's pre-write check. Core
checks its fixed `LINEAGE_TRANSPORT` capability in the immutable Web baseline
before preparing a write, then invokes the verifier on the prepared candidate.
The CLI accepts an event wrapper, expected public SHA, repository checkout and
local proof directory. It never signs, dispatches or writes to a remote branch.

`client_payload.lineage_transport = github-sigstore-bundle-v1` requires exactly
the existing four fields (`public_sha`, `attestation_base64`,
`attestation_sha256`, `receipt_base64`) plus `lineage_transport` and
`sigstore_bundle_base64`. The latter carries the original signed bundle JSON.
Duplicate JSON keys, invalid base64 and nonliteral DSSE payload types are
rejected. The only accepted DSSE payload type is `application/vnd.in-toto+json`.

The official `gh attestation verify --bundle` verifier authenticates the
artifact against GitHub's private Sigstore trust material. Its policy pins:

- Core repository and exact canonical finalizer workflow identity at
  `refs/heads/main`, with GitHub Actions OIDC issuer;
- source digest and signer digest equal to the lineage's Core SHA;
- GitHub-hosted runner, private signing visibility and `workflow_dispatch`;
- verified certificate `runInvocationURI` equal to the declared finalizer run
  and attempt, and `buildSignerURI` equal to the exact canonical workflow;
- a successfully verified timestamp and one unambiguous verification result.

No payload-provided trusted root, insecure override or public-good fallback is
accepted. Hashes alone establish byte identity, not signer authority. The
certificate and verified timestamps are authenticated evidence; a signed
predicate is not a substitute for certificate claims. Existing semantic
validation still checks receipt, public SHA and parent, direct-child Git
relationship, release bundle, intent, acquisition fence and preservation.

Only **absence** of `lineage_transport` selects legacy verification through the
authentic GitHub attestation API. An empty, null, unknown or incomplete transport
does not select legacy. Failure of bundle verification never falls back to API
verification, and absence of API evidence is never success.

## Evidence and test limits

The verifier retains exact `attestation.json`, `receipt.json` and `bundle.json`
bytes. It writes raw `verification.json` only after successful cryptographic
policy and semantic checks. Web keeps this directory under the existing
production verification artifact without changing its root layout or adding
an artifact, job or schedule.

Fourteen focused regression tests model CLI results while exercising the real
semantic lineage validator. They cover identity/content/attempt conflicts,
signature-verifier failure, missing evidence, forbidden downgrade, DSSE Unicode
confusion and identical replay. They run from the existing atomic-publication
owner, including no-release diagnostics. These modeled tests are not a claim of
new Core signing. A separately retained official private GitHub fixture was
verified cryptographically using real `gh`; it is not a Core production receipt.
No diagnostic probe was dispatched, no new Core OIDC certificate was issued by
this local validation, and no production publication or certification occurred.
The prior receipt and editorial repair evidence is preserved, not re-audited or
represented as fresh acquisition evidence.

## Classification and integration conditions

The existing classifier reports the incremental change as `product=true`,
`generated=false`, `release=false`; the domain selector requires `pr-fast-all`.
No file intersects the existing `TRUSTED_AUTOMATION_PATHS` set, and neither the
trusted classifier nor PR finalization machinery is changed. This does **not**
make the publication workflow unprotected operationally: `publish.yml` itself
matches the existing push trigger and its merge can start the automatic Web
pipeline. Observe that pipeline; do not infer a release bump, deployment success
or certification from the no-release classification.

Integrate the base repairs first. Make this Web consumer available and validate
the applicable official compatibility/deployment contracts before activating
the new Core producer. New Core with an old Web consumer must stop at the
pre-write capability check. Old Core with new Web retains authentic legacy
verification, but still cannot overcome the demonstrated private-repository API
storage limitation: it may block safely, not bypass authentication. Drain all
publisher/finalizer runs pinned to old Core before the first new producer write;
independent schedules remain active. Missing runs do not prove absence of durable
reservations, so the later operational preflight must check both.
