# Automatic PR finalization smoke test

This document records the first end-to-end verification of the trusted PR
finalization workflow. The test candidate contains no editorial data and must
be finalized only by the repository automation after its source checks pass.

Acceptance requires one generated finalizer commit, a second check run bound to
that final SHA, and no merge or production publication.
