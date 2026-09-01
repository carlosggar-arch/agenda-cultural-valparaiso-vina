from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
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


def main() -> None:
    test_real_porcelain_status()
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
