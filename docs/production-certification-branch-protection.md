# Production certification branch protection

`state/production-certifications` is an append-only operational state branch. The repository enforces the following invariants in code and CI:

- `.github/workflows/publish.yml` is the only internal writer.
- force-push and branch-deletion commands targeting the state branch are forbidden by `scripts/verify_canonical_main_writer.py`.
- every new certificate stores the SHA-256 of the previous archived certificate.
- every synchronized production deployment is followed by a `certification-watchdog` gate; missing or corrupted evidence is reported as `PRODUCTION_UNCERTIFIED`.

A GitHub repository ruleset should additionally deny force-pushes and deletion for `state/production-certifications`. This is a repository-administration setting rather than repository content, so the in-repository guards remain mandatory even when that platform-level setting is enabled.
