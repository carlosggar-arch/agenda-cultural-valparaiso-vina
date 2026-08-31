from __future__ import annotations

import subprocess
from unittest.mock import patch

from release_finalizer import (
    FINALIZER_ALLOWED_FILES,
    FINALIZER_MARKER,
    GENERATED_RELEASE_FILES,
    GENERATED_RELEASE_FRAGMENTS,
    build_provenance,
    load_squash_pr_evidence,
    release_number_from_text,
    render_release_version,
    replace_index_release_keys,
    validate_fetched_head,
    validate_matching_trees,
    validate_squash_pr_evidence,
    validate_generated_change_sets,
)


def squash_evidence(**overrides: object) -> dict[str, object]:
    evidence: dict[str, object] = {
        "number": 505,
        "state": "MERGED",
        "mergeCommit": {"oid": "d" * 40},
        "headRefOid": "f" * 40,
        "headRefName": "feature/release",
        "headRepository": {"nameWithOwner": "owner/repository"},
        "statusCheckRollup": [
            {"name": "required", "status": "COMPLETED", "conclusion": "SUCCESS"},
        ],
    }
    evidence.update(overrides)
    return evidence


def assert_squash_rejected(evidence: dict[str, object], expected: str) -> None:
    try:
        validate_squash_pr_evidence(
            evidence,
            source_pr=505,
            published_sha="d" * 40,
            published_tree="e" * 40,
        )
    except SystemExit as exc:
        assert expected in str(exc)
    else:
        raise AssertionError(f"invalid squash evidence accepted: {expected}")


def main() -> None:
    assert release_number_from_text("const RELEASE = 225;") == 225
    rendered = render_release_version(226, "a" * 40)
    assert "const RELEASE = 226;" in rendered
    assert "source aaaaaaaaaaaa" in rendered
    shell = '<script type="module" src="./app.js?v=225"></script>\n<script type="module" src="./map-navigation-enhancer.js?v=225"></script>\n'
    updated = replace_index_release_keys(shell, 226)
    assert './app.js?v=226' in updated and './map-navigation-enhancer.js?v=226' in updated
    payload = build_provenance(release=226, base_sha="b" * 40, source_sha="c" * 40, source_pr=446)
    assert payload["release"] == 226
    assert payload["base_sha"] == "b" * 40
    assert payload["source_sha"] == "c" * 40
    assert payload["source_pr"] == 446
    assert payload["generator"] == "app/scripts/release_finalizer.py"
    assert payload["generated_artifacts"] == sorted(GENERATED_RELEASE_FILES)
    assert payload["generated_fragments"] == list(GENERATED_RELEASE_FRAGMENTS)
    assert FINALIZER_MARKER == "[release-finalized]"

    approved_head, head_ref, head_repository = validate_squash_pr_evidence(
        squash_evidence(),
        source_pr=505,
        published_sha="d" * 40,
        published_tree="e" * 40,
    )
    assert approved_head == "f" * 40
    assert head_ref == "feature/release"
    assert head_repository == "owner/repository"
    assert_squash_rejected(squash_evidence(number=504), "PR_MISMATCH")
    assert_squash_rejected(squash_evidence(state="OPEN"), "PR_NOT_MERGED")
    assert_squash_rejected(squash_evidence(mergeCommit={"oid": "a" * 40}), "MERGE_COMMIT_MISMATCH")
    assert_squash_rejected(squash_evidence(headRefOid="not-a-sha"), "HEAD_INVALID")
    assert_squash_rejected(squash_evidence(headRefName=""), "HEAD_METADATA_MISSING")
    assert_squash_rejected(squash_evidence(statusCheckRollup=[]), "CHECKS_MISSING")
    assert_squash_rejected(
        squash_evidence(statusCheckRollup=[{"name": "required", "status": "COMPLETED", "conclusion": "FAILURE"}]),
        "CHECKS_INCOMPLETE",
    )
    validate_fetched_head(approved_head="f" * 40, fetched_head="f" * 40)
    try:
        validate_fetched_head(approved_head="f" * 40, fetched_head="a" * 40)
    except SystemExit as exc:
        assert "HEAD_MOVED" in str(exc)
    else:
        raise AssertionError("a different remote head was accepted")
    validate_matching_trees(published_tree="e" * 40, approved_tree="e" * 40)
    try:
        validate_matching_trees(published_tree="e" * 40, approved_tree="a" * 40)
    except SystemExit as exc:
        assert "TREE_MISMATCH" in str(exc)
    else:
        raise AssertionError("a squash with different content was accepted")
    with patch("release_finalizer.subprocess.check_output", side_effect=subprocess.CalledProcessError(1, ["gh"])):
        try:
            load_squash_pr_evidence(505, "owner/repository")
        except SystemExit as exc:
            assert "METADATA_UNAVAILABLE" in str(exc)
        else:
            raise AssertionError("missing GitHub metadata was accepted")

    generated_sequence = [
        {"app/release-version.js"},
        {"app/index.html"},
        {"app/data/release-provenance.json"},
        {"app/data/release-bundle.json"},
    ]
    combined = validate_generated_change_sets(generated_sequence)
    assert combined <= FINALIZER_ALLOWED_FILES
    assert {
        "app/release-version.js",
        "app/index.html",
        "app/data/release-provenance.json",
        "app/data/release-bundle.json",
    } <= combined
    try:
        validate_generated_change_sets(generated_sequence + [{"app/app.js"}])
    except SystemExit as exc:
        assert "FINALIZER_CHANGED_SOURCE_FILES" in str(exc)
    else:
        raise AssertionError("source changes inside finalization sequence must fail closed")

    try:
        replace_index_release_keys('<script type="module" src="./app.js?v=225"></script>', 226)
    except ValueError:
        pass
    else:
        raise AssertionError("missing canonical module release key must fail closed")
    print("RELEASE_FINALIZER_TESTS_OK")


if __name__ == "__main__":
    main()
