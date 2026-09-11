from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
RELEASE = (ROOT / ".github/workflows/pr-release.yml").read_text(encoding="utf-8")
FINALIZE = (ROOT / ".github/workflows/pr-finalize.yml").read_text(encoding="utf-8")
PUBLISH = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")


def block(text: str, start: str, end: str | None = None) -> str:
    value = text.split(start, 1)[1]
    return value.split(end, 1)[0] if end else value


def workflow_steps(text: str) -> dict[str, str]:
    """Read the existing named-step layout without a runtime YAML dependency."""
    matches = list(re.finditer(r"^      - name: (.+)$", text, flags=re.MULTILINE))
    return {
        match.group(1).strip(): text[match.start():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        for index, match in enumerate(matches)
    }


def step_condition(step: str) -> str:
    match = re.search(r"^        if: (.+(?:\n          .+)*)", step, flags=re.MULTILINE)
    assert match, "a protected finalization step lost its condition"
    return " ".join(match.group(1).replace(">-", "").split())


def require_conjunct(step: str, predicate: str) -> None:
    condition = step_condition(step)
    assert "||" not in condition, "a permissive alternative bypasses the finalization boundary"
    assert predicate in {part.strip() for part in condition.split("&&")}, predicate


def validate_no_release_boundary(text: str) -> None:
    steps = workflow_steps(text)
    authority = steps["Verify release impact from trusted authority"]
    capture = steps["Capture trusted finalization tools"]
    assert text.index("Capture trusted finalization tools") < text.index("Verify release impact from trusted authority")
    assert text.index("Resolve immutable PR snapshot") < text.index("Verify release impact from trusted authority")
    assert text.index("Verify release impact from trusted authority") < text.index("Mint narrowly scoped PR finalizer token")
    assert "ci_change_impact.py" in capture and "/tmp/pr-finalization-tools/" in capture
    assert "id: impact" in authority
    assert "python -S /tmp/pr-finalization-tools/pr_release_automation.py verify-impact" in authority
    assert "gh api" in authority and "/actions/runs/" in authority and "/jobs" in authority
    assert "/logs" in authority or "--log" in authority, "impact must be bound to the source job's explicit logged result"
    assert "github.event.workflow_run.id" in authority and "github.event.workflow_run.run_attempt" in authority
    assert "steps.snapshot.outputs.head_sha" in authority and "steps.snapshot.outputs.base_sha" in authority
    assert "steps.snapshot.outputs.pr_number" in authority
    assert '"$GITHUB_OUTPUT"' in authority
    for forbidden in (
        "actions/create-github-app-token", "steps.app-token.outputs.token", "PR_FINALIZER_TOKEN",
        "secrets.", "actions/checkout", "gh run download", "update-branch", " prepare ",
        "git push", "--method POST", "--method PUT", "--method PATCH", "--method DELETE",
        "workflow_dispatch", "repository_dispatch",
    ):
        assert forbidden not in authority, f"read-only impact verification performs {forbidden}"

    for name in (
        "Mint narrowly scoped PR finalizer token",
        "Refresh safely when main advanced",
        "Verify successful source-validation handoff",
    ):
        require_conjunct(steps[name], "steps.impact.outputs.release == 'true'")
        require_conjunct(steps[name], "steps.snapshot.outputs.draft != 'true'")
        require_conjunct(steps[name], "steps.snapshot.outputs.replay != 'true'")
    for name in (
        "Prepare exact finalizer commit without credentials",
        "Revalidate immutable head and base",
        "Fast-forward the PR branch to the validated finalizer",
    ):
        require_conjunct(steps[name], "steps.handoff.outputs.ready == 'true'")

    noop = steps["Validated no-release candidate needs no finalizer"]
    require_conjunct(noop, "steps.impact.outputs.no_release == 'true'")
    assert "run: echo " in noop, "the no-release terminal step must remain declarative"
    statement = noop.split("        run:", 1)[1].strip()
    assert len(statement.splitlines()) == 1
    assert not any(token in statement for token in (";", "&&", "||", "$(", "`")), "the no-op must not run shell substitutions or chained commands"
    for forbidden in (
        "uses:", "env:", "gh ", "python ", "download", "update-branch",
        "PR_FINALIZER", "prepare", "push", "dispatch", "commit",
    ):
        assert forbidden not in noop, f"the no-release path performs {forbidden}"
    require_conjunct(steps["Failed validation remains blocking"], "steps.impact.outputs.no_release != 'true'")
    assert "exit 1" in steps["Failed validation remains blocking"]


def validate_trusted_bundle_imports(text: str) -> None:
    capture = workflow_steps(text)["Capture trusted finalization tools"]
    match = re.search(r"cp app/scripts/\{([^}]+)\} /tmp/pr-finalization-tools/", capture)
    assert match, "the captured trusted bundle must be explicit"
    names = {name.strip() for name in match.group(1).split(",")}
    assert "ci_change_impact.py" in names
    assert "core_publication_lineage.py" in names, "release_finalizer imports its lineage verifier before CLI dispatch"
    assert all(Path(name).name == name and name.endswith(".py") for name in names)
    for name in ("Verify successful source-validation handoff", "Prepare exact finalizer commit without credentials"):
        guard = re.search(r"protected='([^']+)'", workflow_steps(text)[name])
        assert guard, "trusted tools require the existing manual-finalization boundary"
        assert all(re.fullmatch(guard.group(1), f"app/scripts/{filename}") for filename in names), "a trusted dependency is missing from the protected paths"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    with tempfile.TemporaryDirectory(prefix="pr-finalizer-trusted-bundle-") as temporary:
        bundle = Path(temporary)
        for name in names:
            shutil.copy2(ROOT / "app/scripts" / name, bundle / name)
        result = subprocess.run(
            [sys.executable, "-S", str(bundle / "pr_release_automation.py"), "--help"],
            cwd=bundle, env=environment, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, f"isolated trusted bundle failed before verification: {result.stderr}"
        assert "verify-impact" in result.stdout


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
    validate_no_release_boundary(FINALIZE)
    validate_trusted_bundle_imports(FINALIZE)

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

    refresh = block(PUBLISH, "  refresh-open-release-prs:\n")
    assert "actions/create-github-app-token@v2" in refresh
    assert "PR_FINALIZER_APP_ID" in refresh and "PR_FINALIZER_APP_PRIVATE_KEY" in refresh
    assert "repositories: agenda-cultural-valparaiso-vina" in refresh
    assert "permission-contents: write" in refresh and "permission-pull-requests: write" in refresh
    assert "      contents: read" in refresh and "      pull-requests: read" in refresh
    assert "      contents: write" not in refresh and "      pull-requests: write" not in refresh
    assert 'GH_TOKEN: ""' in refresh, "job must shadow the workflow-level GITHUB_TOKEN alias"
    assert "skip-token-revoke" not in refresh, "App token must be revoked automatically after the job"
    update = block(refresh, "Refresh open same-repository PR candidates onto published main")
    assert "GH_TOKEN: ${{ steps.app-token.outputs.token }}" in update
    assert "GH_TOKEN: ${{ github.token }}" not in update, "PR refresh must never fall back to GITHUB_TOKEN"
    assert ".draft == false" in update and ".head.repo.full_name == .base.repo.full_name" in update
    assert "expected_head_sha=\"$head_sha\"" in update, "PR refresh must reject concurrent head changes"
    assert "HTTP (409|422)" in update and "continue" in update
    assert "PR finalizer App update failed" in update and "exit 1" in update
    assert "without fallback credentials" in update
    assert "actions/checkout" not in refresh, "App token job must not execute code from a PR checkout"
    assert "git push" not in refresh and "gh pr merge" not in refresh
    print("PR_FINALIZATION_WORKFLOW_TESTS_OK security=split validation=read-only update=fast-forward")


if __name__ == "__main__":
    main()
