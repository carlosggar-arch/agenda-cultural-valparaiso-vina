# Production certification branch protection

`state/production-certifications` is an append-only operational state branch. The repository enforces the following invariants in code and CI:

- `.github/workflows/publish.yml` is the only internal writer.
- force-push and branch-deletion commands targeting the state branch are forbidden by `scripts/verify_canonical_main_writer.py`.
- every new certificate stores the SHA-256 of the previous archived certificate.
- every synchronized production deployment is followed by a `certification-watchdog` gate; missing or corrupted evidence is reported as `PRODUCTION_UNCERTIFIED`.

A GitHub repository ruleset should additionally deny force-pushes and deletion for `state/production-certifications`. This is a repository-administration setting rather than repository content, so the in-repository guards remain mandatory even when that platform-level setting is enabled.

## Merge strategy for finalized releases

A normal merge that preserves the approved source and `[release-finalized]` commits as ancestors is preferred because Git can prove the complete lineage locally.

Squash merge remains supported only through the same `release_finalizer.py` authority. Its published check fails closed unless GitHub proves that the published commit is the recorded merge commit of the merged source PR, the remote PR branch still resolves to the approved finalizer head, every reported head check completed successfully, the approved source-to-finalizer boundary remains valid, and the published and approved heads have exactly the same Git tree SHA. Tree equality prevents a squash from adding, removing, or rewriting any byte while the PR metadata and original boundary retain authorship and review lineage.
