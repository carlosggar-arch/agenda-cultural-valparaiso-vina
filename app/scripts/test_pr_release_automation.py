from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import subprocess
import tempfile
from unittest.mock import patch

import pr_release_automation as automation


def rejects(callable_, expected: str) -> None:
    try:
        callable_()
    except SystemExit as exc:
        assert expected in str(exc)
    else:
        raise AssertionError(f"expected rejection: {expected}")


def run_git(root: Path, *args: str) -> None:
    subprocess.check_call(["git", *args], cwd=root, stdout=subprocess.DEVNULL)


def test_real_porcelain_status() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        run_git(root, "init", "-q")
        run_git(root, "config", "user.name", "PR automation test")
        run_git(root, "config", "user.email", "pr-automation@example.invalid")
        tracked = root / "tracked.txt"
        second = root / "second.txt"
        spaced = root / "tracked path with spaces.txt"
        for path in (tracked, second, spaced):
            path.write_text("base\n", encoding="utf-8")
        run_git(root, "add", "--", tracked.name, second.name, spaced.name)
        run_git(root, "commit", "-qm", "fixture")

        tracked.write_text("unstaged\n", encoding="utf-8")
        assert automation.status_paths(root) == {"tracked.txt"}

        run_git(root, "add", "--", tracked.name)
        assert automation.status_paths(root) == {"tracked.txt"}

        untracked = root / "untracked path with spaces.txt"
        untracked.write_text("new\n", encoding="utf-8")
        second.write_text("also modified\n", encoding="utf-8")
        assert automation.status_paths(root) == {
            "tracked.txt",
            "second.txt",
            "untracked path with spaces.txt",
        }

        run_git(root, "add", "--", spaced.name)
        spaced.write_text("staged and unstaged\n", encoding="utf-8")
        assert "tracked path with spaces.txt" in automation.status_paths(root)

        rejects(
            lambda: automation.require_generated_only({"untracked path with spaces.txt"}),
            "UNEXPECTED_OUTPUT",
        )


def test_trusted_source_impact() -> None:
    """Use actual Git objects, but no GitHub, credentials or release artifacts."""
    repository = "example/agenda"
    pr_number, run_id, run_attempt = 23, 1701, 1
    step_names = [
        "Fetch current integration base",
        "Classify release impact against current main",
        "Run independent release diagnostics and aggregate failures",
        "Require or transiently prepare canonical finalization",
        "No release surface affected",
        "Publish one aggregate diagnostic summary",
    ]

    def git_value(root: Path, *args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

    def source_run(head: str, base: str, *, release: bool = False) -> dict:
        return {
            "id": run_id,
            "run_attempt": run_attempt,
            "name": "PR release gate",
            "path": ".github/workflows/pr-release.yml",
            "event": "pull_request",
            "head_sha": head,
            "head_branch": "codex/example",
            "status": "completed",
            "conclusion": "failure" if release else "success",
            "repository": {"full_name": repository},
            "head_repository": {"full_name": repository},
            "pull_requests": [{
                "number": pr_number,
                "head": {"sha": head, "ref": "codex/example", "repo": {"id": 31, "full_name": repository}},
                "base": {"sha": base, "ref": "main", "repo": {"id": 31, "full_name": repository}},
            }],
        }

    def source_jobs(head: str, *, release: bool = False) -> dict:
        steps = []
        for number, name in enumerate(step_names, start=1):
            skipped = name == (
                "No release surface affected" if release
                else "Require or transiently prepare canonical finalization"
            )
            steps.append({"name": name, "number": number, "status": "completed",
                          "conclusion": "skipped" if skipped else "success"})
        if release:
            steps.append({"name": "Keep source-only candidate blocked until final commit exists",
                          "number": len(steps) + 1, "status": "completed", "conclusion": "failure"})
        return {"total_count": 1, "jobs": [{
            "id": 2901, "run_id": run_id, "run_attempt": run_attempt,
            "name": "release-guard", "status": "completed", "head_sha": head,
            "conclusion": "failure" if release else "success", "steps": steps,
        }]}

    def source_log(head: str, base: str, *, release: bool = False, count: int = 1) -> str:
        lines = [f"RELEASE_QUEUE_BASE={base}", f"RELEASE_QUEUE_CANDIDATE={head}",
                 "CI_IMPACT", "product=true", "generated=false",
                 f"release={'true' if release else 'false'}", f"changed_count={count}"]
        return "\n".join(
            f"release-guard\tUNKNOWN STEP\t2026-09-11T00:00:{index:02d}.1234567Z {line}"
            for index, line in enumerate(lines)
        ) + "\n"

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        run_git(root, "init", "-q")
        run_git(root, "config", "user.name", "Source impact test")
        run_git(root, "config", "user.email", "source-impact@example.invalid")
        run_git(root, "config", "core.autocrlf", "false")
        classifier = root / "app/scripts/ci_change_impact.py"
        workflow = root / ".github/workflows/pr-release.yml"
        for target, source in (
            (classifier, automation.ROOT / "app/scripts/ci_change_impact.py"),
            (workflow, automation.ROOT / ".github/workflows/pr-release.yml"),
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        run_git(root, "add", "--", "app", ".github")
        run_git(root, "commit", "-qm", "Trusted source authority")
        base = git_value(root, "rev-parse", "HEAD")
        fixture = root / "app/scripts/non_release_fixture.py"
        fixture.write_text("VALUE = 1\n", encoding="utf-8")
        run_git(root, "add", "--", fixture.relative_to(root).as_posix())
        run_git(root, "commit", "-qm", "Non-release script change")
        head = git_value(root, "rev-parse", "HEAD")
        arguments = {
            "root": root, "repository": repository, "pr_number": pr_number,
            "run_id": run_id, "run_attempt": run_attempt, "validated_head": head,
            "current_head": head, "current_base": base, "authority_sha": base,
            "run": source_run(head, base), "jobs": source_jobs(head), "log": source_log(head, base),
        }

        def verify(values: dict) -> dict:
            before = (git_value(root, "rev-parse", "HEAD"), automation.status_paths(root))
            real_check_output = subprocess.check_output
            real_run = subprocess.run

            def read_only_git(command, *args, **kwargs):
                assert command[0] == "git", f"unexpected external process: {command}"
                assert command[1] in {"show", "diff", "rev-parse", "merge-base", "cat-file", "status"}, command
                return real_check_output(command, *args, **kwargs)

            def read_only_run(command, *args, **kwargs):
                assert command[0] == "git", f"unexpected external process: {command}"
                assert command[1] in {"show", "diff", "rev-parse", "merge-base", "cat-file", "status"}, command
                return real_run(command, *args, **kwargs)

            with (
                patch.object(automation.subprocess, "check_output", side_effect=read_only_git),
                patch.object(automation.subprocess, "run", side_effect=read_only_run),
                patch.object(automation.subprocess, "check_call", side_effect=AssertionError("external mutation forbidden")),
                patch.object(automation, "prepare", side_effect=AssertionError("release preparation forbidden")),
                patch.object(automation.release_finalizer, "prepare_release", side_effect=AssertionError("release output forbidden")),
            ):
                result = automation.verify_source_impact(**values)
            after = (git_value(root, "rev-parse", "HEAD"), automation.status_paths(root))
            assert before == after, "impact verification changed the candidate"
            assert not (root / "app/data/release-bundle.json").exists()
            assert not (root / "handoff.json").exists()
            return result

        result = verify(arguments)
        assert result["release"] is False and result["no_release"] is True
        assert result["source_head"] == head and result["source_base"] == base
        assert re.fullmatch(r"[0-9a-f]{64}", result["paths_sha256"])
        assert verify(arguments) == result, "same run/attempt must yield the same no-op proof"
        with_bom = deepcopy(arguments)
        with_bom["log"] = with_bom["log"].replace("\t2026-", "\t\ufeff2026-", 1)
        assert verify(with_bom) == result, "gh can retain the source log's initial BOM"

        rejected = 0

        def must_reject(label: str, values: dict) -> None:
            nonlocal rejected
            try:
                verify(values)
            except SystemExit as exc:
                assert str(exc).startswith("PR_FINALIZATION_IMPACT_INVALID:"), str(exc)
                rejected += 1
            else:
                raise AssertionError(f"untrusted impact accepted: {label}")

        for key, bad in (
            ("id", run_id + 1), ("run_attempt", run_attempt + 1),
            ("name", "Different workflow"), ("path", ".github/workflows/other.yml"),
            ("event", "push"), ("status", "in_progress"), ("head_sha", "b" * 40),
            ("repository", {"full_name": "other/agenda"}),
            ("head_repository", {"full_name": "fork/agenda"}),
            ("pull_requests", []),
        ):
            changed = deepcopy(arguments)
            changed["run"][key] = bad
            must_reject(f"run {key}", changed)
        for conclusion in ("failure", "cancelled", "timed_out", "skipped", None):
            changed = deepcopy(arguments)
            changed["run"]["conclusion"] = conclusion
            must_reject(f"no-release conclusion {conclusion}", changed)
        for key, bad in (("number", pr_number + 1), ("head", {"sha": "c" * 40}),
                         ("base", {"sha": base, "ref": "other", "repo": {"id": 31, "full_name": repository}})):
            changed = deepcopy(arguments)
            changed["run"]["pull_requests"][0][key] = bad
            must_reject(f"PR identity {key}", changed)
        for key in ("current_head", "validated_head", "current_base"):
            changed = deepcopy(arguments)
            changed[key] = "d" * 40
            must_reject(key, changed)
        for key, bad in (("run_id", run_id + 1), ("run_attempt", run_attempt + 1),
                         ("name", "other-job"), ("status", "in_progress"), ("conclusion", "failure")):
            changed = deepcopy(arguments)
            changed["jobs"]["jobs"][0][key] = bad
            must_reject(f"job {key}", changed)
        for step_index in range(len(step_names)):
            changed = deepcopy(arguments)
            step = changed["jobs"]["jobs"][0]["steps"][step_index]
            step["conclusion"] = "success" if step["conclusion"] == "skipped" else "skipped"
            must_reject(f"required step {step['name']}", changed)
        for old, new in (
            ("release=false", "release=unknown"), ("release=false", "release=True"),
            ("release=false", "release=true"), ("release=false", "release=null"),
            ("product=true", "product=false"), ("generated=false", "generated=true"),
            ("changed_count=1", "changed_count=2"), ("CI_IMPACT", "UNKNOWN_IMPACT"),
            (f"RELEASE_QUEUE_BASE={base}", f"RELEASE_QUEUE_BASE={'e' * 40}"),
            (f"RELEASE_QUEUE_CANDIDATE={head}", f"RELEASE_QUEUE_CANDIDATE={'f' * 40}"),
        ):
            changed = deepcopy(arguments)
            changed["log"] = changed["log"].replace(old, new)
            must_reject(f"log {old} -> {new}", changed)
        for duplicate in (arguments["log"], arguments["log"].splitlines()[0] + "\n"):
            changed = deepcopy(arguments)
            changed["log"] += duplicate
            must_reject("duplicate log authority", changed)
        changed = deepcopy(arguments)
        changed["jobs"]["jobs"].append(deepcopy(changed["jobs"]["jobs"][0]))
        must_reject("duplicate release job", changed)
        changed = deepcopy(arguments)
        changed["run"]["pull_requests"].append(deepcopy(changed["run"]["pull_requests"][0]))
        must_reject("ambiguous PR identity", changed)
        changed = deepcopy(arguments)
        changed["run"]["pull_requests"][0]["head"]["repo"]["id"] = 32
        must_reject("fork repository identity", changed)
        changed = deepcopy(arguments)
        changed["jobs"]["jobs"][0]["steps"].pop()
        must_reject("missing diagnostic summary", changed)
        for bad_classification in (
            {"product": True, "generated": False},
            {"product": True, "generated": False, "release": None},
            {"product": True, "generated": False, "release": "false"},
            {"product": True, "generated": False, "release": 0},
        ):
            with patch.object(automation.ci_change_impact, "classify", return_value=bad_classification):
                must_reject("unknown trusted classifier contract", deepcopy(arguments))

        # A new main revision must never be silently refreshed by the no-op path.
        run_git(root, "checkout", "--detach", "-q", base)
        (root / "README.md").write_text("New main revision\n", encoding="utf-8")
        run_git(root, "add", "--", "README.md")
        run_git(root, "commit", "-qm", "Main advances independently")
        new_base = git_value(root, "rev-parse", "HEAD")
        changed = deepcopy(arguments)
        changed["current_base"] = new_base
        changed["authority_sha"] = new_base
        must_reject("actual advanced main", changed)
        changed["run"] = source_run(head, new_base)
        changed["log"] = source_log(head, new_base)
        must_reject("base was never in the source ancestry", changed)

        # Existing release candidates remain release candidates, including the
        # source-only gate's deliberate failure while its handoff awaits use.
        run_git(root, "checkout", "--detach", "-q", head)
        (root / "app/app.js").write_text("export const releaseFixture = true;\n", encoding="utf-8")
        run_git(root, "add", "--", "app/app.js")
        run_git(root, "commit", "-qm", "Release surface fixture")
        release_head = git_value(root, "rev-parse", "HEAD")
        release_arguments = dict(arguments, validated_head=release_head, current_head=release_head,
                                 run=source_run(release_head, base, release=True), jobs=source_jobs(release_head, release=True),
                                 log=source_log(release_head, base, release=True, count=2))
        release_result = verify(release_arguments)
        assert release_result["release"] is True and release_result["no_release"] is False
        for handoff_ready, expected_action in ((False, "block"), (True, "finalize")):
            decision = automation.decide_lifecycle(
                validated_head=release_head, current_head=release_head, current_parent=head,
                base_is_ancestor=True, validation_passed=True, handoff_ready=handoff_ready,
                current_subject="Release surface fixture",
            )
            assert decision.action == expected_action, "release proof never replaces its handoff"
        release_arguments["current_base"] = new_base
        release_arguments["authority_sha"] = new_base
        assert verify(release_arguments)["no_release"] is False, "release base refresh contract must remain available"

        # A PR cannot supply its own classifier or validator to manufacture a
        # trusted no-release assertion, even if its run says success.
        for relative in ("app/scripts/ci_change_impact.py", ".github/workflows/pr-release.yml"):
            run_git(root, "checkout", "--detach", "-q", head)
            path = root / relative
            path.write_text(path.read_text(encoding="utf-8") + "\n# Candidate changes trusted authority\n", encoding="utf-8")
            run_git(root, "add", "--", relative)
            run_git(root, "commit", "-qm", "Untrusted authority mutation")
            mutated_head = git_value(root, "rev-parse", "HEAD")
            changed = dict(arguments, validated_head=mutated_head, current_head=mutated_head,
                           run=source_run(mutated_head, base), jobs=source_jobs(mutated_head),
                           log=source_log(mutated_head, base, count=2))
            must_reject(f"candidate authority {relative}", changed)
        print(f"PR_SOURCE_IMPACT_TESTS_OK rejected={rejected} no_release=artifact-free release=legacy")


def main() -> None:
    test_real_porcelain_status()
    test_trusted_source_impact()
    assert automation.is_finalizer_commit("[release-finalized] Canonical")
    assert not automation.is_finalizer_commit("Improve titles")
    automation.require_snapshot(expected="a" * 40, actual="a" * 40, label="HEAD")
    rejects(
        lambda: automation.require_snapshot(expected="a" * 40, actual="b" * 40, label="HEAD"),
        "HEAD_MOVED",
    )
    automation.require_automatic_scope({"app/app.js", "assets/agenda.js"})
    rejects(
        lambda: automation.require_automatic_scope({"app/scripts/release_finalizer.py"}),
        "MANUAL_REQUIRED",
    )
    allowed = set(automation.release_finalizer.GENERATED_RELEASE_FILES) | {"app/index.html"}
    automation.require_generated_only(allowed)
    rejects(lambda: automation.require_generated_only(allowed | {"agenda_web.json"}), "UNEXPECTED_OUTPUT")
    rejects(lambda: automation.require_generated_only({"app/release-version.js"}), "REQUIRED_OUTPUT_MISSING")

    report = automation.aggregate_diagnostics(
        [
            automation.Diagnostic("syntax", "failure"),
            automation.Diagnostic("architecture", "failure"),
            automation.Diagnostic("browser", "success", requires=("syntax",)),
            automation.Diagnostic("parity", "skipped", requires=("browser",)),
        ]
    )
    assert report == {
        "passed": [],
        "failed": ["architecture", "syntax"],
        "not_run": ["browser", "parity"],
        "blocking": True,
    }
    assert automation.aggregate_diagnostics(
        [automation.Diagnostic("syntax", "success"), automation.Diagnostic("browser", "success")]
    )["blocking"] is False

    source = "s" * 40
    finalizer = "f" * 40
    assert automation.decide_lifecycle(
        validated_head=source, current_head=source, current_parent="p" * 40,
        base_is_ancestor=True, validation_passed=True, handoff_ready=True,
        current_subject="Improve source",
    ) == automation.LifecycleDecision("finalize", "validated_source")
    assert automation.decide_lifecycle(
        validated_head=source, current_head=finalizer, current_parent=source,
        base_is_ancestor=True, validation_passed=True, handoff_ready=True,
        current_subject="[release-finalized] Finalize",
    ) == automation.LifecycleDecision("noop", "exact_finalizer_already_present")
    assert automation.decide_lifecycle(
        validated_head=finalizer, current_head=finalizer, current_parent=source,
        base_is_ancestor=False, validation_passed=True, handoff_ready=True,
        current_subject="[release-finalized] Finalize",
    ) == automation.LifecycleDecision("refresh", "base_moved")
    assert automation.decide_lifecycle(
        validated_head=source, current_head="n" * 40, current_parent=source,
        base_is_ancestor=True, validation_passed=True, handoff_ready=True,
        current_subject="New source change",
    ) == automation.LifecycleDecision("block", "head_moved")
    assert automation.decide_lifecycle(
        validated_head=source, current_head=source, current_parent="p" * 40,
        base_is_ancestor=True, validation_passed=False, handoff_ready=False,
        current_subject="Improve source",
    ) == automation.LifecycleDecision("block", "validation_failed")
    assert automation.decide_lifecycle(
        validated_head=source, current_head=finalizer, current_parent="x" * 40,
        base_is_ancestor=True, validation_passed=True, handoff_ready=True,
        current_subject="[release-finalized] Unrelated",
    ) == automation.LifecycleDecision("block", "head_moved")
    automation.require_finalizer_boundary(source=source, parent=source)
    rejects(lambda: automation.require_finalizer_boundary(source=source, parent="x" * 40), "PARENT_MOVED")

    with patch.object(
        automation,
        "git",
        side_effect=["s" * 40, "Improve canonical titles", "app/app.js"],
    ), patch.object(automation, "git_check", return_value=True), patch.object(
        automation.release_finalizer, "prepare_release"
    ) as prepare_release, patch.object(
        automation, "status_paths", return_value=set(automation.FINALIZER_REQUIRED_FILES)
    ):
        assert automation.prepare(base="b" * 40, source="s" * 40, source_pr=509, commit=False) == "s" * 40
        prepare_release.assert_called_once_with(base_ref="b" * 40, source_sha="s" * 40, source_pr=509)

    with patch.object(automation, "git", side_effect=["f" * 40, "[release-finalized] Done"]), patch.object(
        automation, "git_check", return_value=True
    ), patch.object(automation.release_finalizer, "prepare_release") as manual:
        assert automation.prepare(base="b" * 40, source="f" * 40, source_pr=508, commit=True) == "f" * 40
        manual.assert_not_called()
    print("PR_RELEASE_AUTOMATION_TESTS_OK")


if __name__ == "__main__":
    main()
