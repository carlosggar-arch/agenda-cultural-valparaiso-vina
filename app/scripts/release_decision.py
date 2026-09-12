"""Versioned evidence shared by trusted PR finalization and deployment routing.

This is a binding, not a signature or an approval: callers must first verify the
source gate using the classifier from the exact integration base.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def bind_source_decision(*, root: Path, repository: str, impact: dict) -> dict:
    if type(impact.get("release")) is not bool or impact.get("no_release") is not (not impact["release"]):
        raise SystemExit("RELEASE_DECISION_INVALID:classification")
    base, head = impact["source_base"], impact["source_head"]
    diff = subprocess.check_output(
        ["git", "diff", "--binary", "--full-index", "--no-ext-diff", "--no-renames", base, head], cwd=root
    )
    return {
        **impact, "contract": "verified-release-decision", "schema_version": 1,
        "repository": repository, "diff_sha256": hashlib.sha256(diff).hexdigest(),
    }
