from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE = (ROOT / ".github/workflows/pr-release.yml").read_text(encoding="utf-8")
FINALIZE = (ROOT / ".github/workflows/pr-finalize.yml").read_text(encoding="utf-8")


def block(text: str, start: str, end: str | None = None) -> str:
    value = text.split(start, 1)[1]
    return value.split(end, 1)[0] if end else value


def main() -> None:
    assert "permissions:\n  contents: read" in RELEASE
    assert "contents: write" not in RELEASE
    assert "Run independent release diagnostics and aggregate failures" in RELEASE
    diagnostics = block(RELEASE, "Run independent release diagnostics", "Require or transiently")
    for command in (
        "test_release_finalizer.py",
        "test_atomic_publication_contract.py",
        "verify_canonical_main_writer.py",
        "pr_release_automation.py summarize",
    ):
        assert command in diagnostics
    assert "set +e" in diagnostics, "independent diagnostics must all run"
    assert "Publish one aggregate diagnostic summary" in RELEASE
    assert "if: always()" in RELEASE
    for diagnostic in ("diagnostics", "finalization", "preflight", "browser_setup", "compile_shell", "contracts", "browser", "parity"):
        assert f"steps.{diagnostic}.outcome" in RELEASE
    assert "Bind successful source validation to an immutable handoff" in RELEASE
    assert "pr-finalization-ready-${{ github.event.pull_request.number }}" in RELEASE
    assert "Keep source-only candidate blocked until final commit exists" in RELEASE
    assert "PR_FINALIZATION_COMMIT_PENDING" in RELEASE

    triggers = FINALIZE.split("permissions:", 1)[0]
    assert "workflow_run:" in triggers and 'workflows: ["PR release gate"]' in triggers
    assert "pull_request:" not in triggers and "push:" not in triggers and "workflow_dispatch:" not in triggers
    assert "actions: read" in FINALIZE and "contents: read" in FINALIZE and "pull-requests: read" in FINALIZE
    assert "contents: write" not in FINALIZE and "pull-requests: write" not in FINALIZE
    assert "ref: main" in FINALIZE and "persist-credentials: false" in FINALIZE
    assert "github.event.workflow_run.pull_requests[0].head.sha" in FINALIZE
    assert 'test "$parent" = "$VALIDATED_HEAD"' in FINALIZE
    assert "PR_FINALIZATION_EXACT_REPLAY" in FINALIZE
    assert 'test "$(git rev-parse origin/main)" = "$BASE_SHA"' in FINALIZE
    assert 'test "$(git rev-parse HEAD^)" = "$SOURCE_SHA"' in FINALIZE
    assert 'test "$(gh api' in FINALIZE and '--jq .head.sha)" = "$SOURCE_SHA"' in FINALIZE
    assert "expected_head_sha" in FINALIZE and "update-branch" in FINALIZE
    assert "git merge-tree --write-tree" in FINALIZE
    assert "merge_diagnostics" in FINALIZE
    assert "PR requires conflict resolution" in FINALIZE
    assert "actions/create-github-app-token@v2" in FINALIZE
    assert "PR_FINALIZER_APP_ID" in FINALIZE and "PR_FINALIZER_APP_PRIVATE_KEY" in FINALIZE
    assert "Verify successful source-validation handoff" in FINALIZE
    assert "gh run download" in FINALIZE
    for field in ("schema_version", "repository", "workflow", "workflow_ref", "source_sha", "base_sha", "workflow_run_id", "run_attempt", "diagnostics"):
        assert f".{field}" in FINALIZE
        assert f"{field}:" in RELEASE

    prepare = block(FINALIZE, "Prepare exact finalizer commit without credentials", "Revalidate immutable")
    assert "GH_TOKEN" not in prepare and "PR_FINALIZER_TOKEN" not in prepare
    assert "python -S app/scripts/pr_release_automation.py prepare" in prepare
    assert "--commit" in prepare
    assert "Manual finalization required" in prepare
    revalidate = block(FINALIZE, "Revalidate immutable head and base", "Fast-forward the PR branch")
    assert "release_finalizer.py --check" in revalidate
    push = block(FINALIZE, "Fast-forward the PR branch", "Draft PR remains")
    assert 'push origin "HEAD:refs/heads/${HEAD_REF}"' in push
    assert "PR_FINALIZER_TOKEN" in push and "github.token" not in push
    assert "core.hooksPath=/dev/null" in push
    assert "downstream_checks=pull_request_synchronize" in push
    assert "main" not in push and "cloudflare-preview" not in push

    assert "PR_FINALIZATION_ALREADY_COMPLETE" in FINALIZE
    assert "steps.snapshot.outputs.replay != 'true'" in FINALIZE
    assert "PR_FINALIZATION_BLOCKED_BY_VALIDATION" in FINALIZE
    assert "git push --force" not in FINALIZE and "force-with-lease" not in FINALIZE
    assert "--admin" not in FINALIZE
    assert "gh pr merge" not in FINALIZE and "gh pr review" not in FINALIZE
    assert "agenda_web.json" not in FINALIZE and "evento/" not in FINALIZE and ".ics" not in FINALIZE
    print("PR_FINALIZATION_WORKFLOW_TESTS_OK security=split validation=read-only update=fast-forward")


if __name__ == "__main__":
    main()
