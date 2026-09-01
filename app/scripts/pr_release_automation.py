from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import release_finalizer


ROOT = Path(__file__).resolve().parents[2]
FINALIZER_MESSAGE = "[release-finalized] Finalize canonical PR candidate"
FINALIZER_REQUIRED_FILES = frozenset(
    {
        "app/data/release-bundle.json",
        "app/data/release-provenance.json",
        "app/index.html",
        "app/release-version.js",
    }
)
TRUSTED_AUTOMATION_PATHS = frozenset(
    {
        ".github/workflows/pr-finalize.yml",
        ".github/workflows/pr-release.yml",
        "app/scripts/generate_runtime_contracts.py",
        "app/scripts/pr_release_automation.py",
        "app/scripts/release_bundle.py",
        "app/scripts/release_finalizer.py",
    }
)


@dataclass(frozen=True)
class Diagnostic:
    name: str
    result: str
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class LifecycleDecision:
    action: str
    reason: str


def decide_lifecycle(
    *, validated_head: str, current_head: str, current_parent: str | None,
    base_is_ancestor: bool, validation_passed: bool, handoff_ready: bool,
    current_subject: str,
) -> LifecycleDecision:
    """Plan a trusted action without treating a marker as sufficient authority."""
    exact_replay = (
        current_head != validated_head
        and is_finalizer_commit(current_subject)
        and current_parent == validated_head
    )
    if current_head != validated_head and not exact_replay:
        return LifecycleDecision("block", "head_moved")
    if not base_is_ancestor:
        return LifecycleDecision("refresh", "base_moved")
    if exact_replay or (current_head == validated_head and is_finalizer_commit(current_subject)):
        return LifecycleDecision("noop", "exact_finalizer_already_present")
    if not validation_passed or not handoff_ready:
        return LifecycleDecision("block", "validation_failed")
    return LifecycleDecision("finalize", "validated_source")


def require_finalizer_boundary(*, source: str, parent: str) -> None:
    require_snapshot(expected=source, actual=parent, label="PARENT")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_check(*args: str) -> bool:
    return subprocess.run(
        ["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def changed_paths(base: str, head: str) -> set[str]:
    output = git("diff", "--name-only", f"{base}...{head}")
    return {line for line in output.splitlines() if line}


def is_finalizer_commit(subject: str) -> bool:
    return release_finalizer.FINALIZER_MARKER in subject


def require_snapshot(*, expected: str, actual: str, label: str) -> None:
    if expected != actual:
        raise SystemExit(f"PR_FINALIZATION_{label}_MOVED expected={expected} actual={actual}")


def require_automatic_scope(paths: set[str]) -> None:
    protected = sorted(paths & TRUSTED_AUTOMATION_PATHS)
    if protected:
        raise SystemExit("PR_FINALIZATION_MANUAL_REQUIRED paths=" + ",".join(protected))


def require_generated_only(paths: set[str]) -> None:
    unexpected = sorted(paths - release_finalizer.FINALIZER_ALLOWED_FILES)
    if unexpected:
        raise SystemExit("PR_FINALIZATION_UNEXPECTED_OUTPUT paths=" + ",".join(unexpected))
    missing = sorted(FINALIZER_REQUIRED_FILES - paths)
    if missing:
        raise SystemExit("PR_FINALIZATION_REQUIRED_OUTPUT_MISSING paths=" + ",".join(missing))


def aggregate_diagnostics(rows: list[Diagnostic]) -> dict[str, object]:
    by_name = {row.name: row for row in rows}
    if len(by_name) != len(rows):
        raise ValueError("diagnostic names must be unique")
    normalized: dict[str, str] = {}
    for row in rows:
        if row.result not in {"success", "failure", "skipped"}:
            raise ValueError(f"invalid diagnostic result: {row.name}={row.result}")
        unmet = [name for name in row.requires if normalized.get(name) != "success"]
        result = "skipped" if unmet else row.result
        normalized[row.name] = result
    return {
        "passed": sorted(name for name, result in normalized.items() if result == "success"),
        "failed": sorted(name for name, result in normalized.items() if result == "failure"),
        "not_run": sorted(name for name, result in normalized.items() if result == "skipped"),
        "blocking": any(result == "failure" for result in normalized.values()),
    }


def prepare(*, base: str, source: str, source_pr: int, commit: bool) -> str:
    head = git("rev-parse", "HEAD")
    require_snapshot(expected=source, actual=head, label="HEAD")
    if not git_check("merge-base", "--is-ancestor", base, source):
        raise SystemExit(f"PR_FINALIZATION_BASE_NOT_ANCESTOR base={base} source={source}")
    subject = git("log", "-1", "--format=%s", source)
    if is_finalizer_commit(subject):
        print(f"PR_FINALIZATION_ALREADY_COMPLETE head={source}")
        return source
    source_paths = changed_paths(base, source)
    require_automatic_scope(source_paths)
    release_finalizer.prepare_release(base_ref=base, source_sha=source, source_pr=source_pr)
    generated = {
        line
        for line in git("status", "--short").splitlines()
        if line
        for line in [line[3:]]
    }
    require_generated_only(generated)
    if not commit:
        print(f"PR_FINALIZATION_PREPARED_TRANSIENT source={source} pr={source_pr}")
        return source
    subprocess.check_call(
        ["git", "add", "--", *sorted(release_finalizer.FINALIZER_ALLOWED_FILES)], cwd=ROOT
    )
    subprocess.check_call(["git", "commit", "-m", FINALIZER_MESSAGE], cwd=ROOT)
    finalizer = git("rev-parse", "HEAD")
    require_snapshot(expected=source, actual=git("rev-parse", "HEAD^"), label="PARENT")
    release_finalizer.check_candidate(base_ref=base, finalizer_ref=finalizer)
    print(f"PR_FINALIZATION_COMMIT_READY source={source} finalizer={finalizer} pr={source_pr}")
    return finalizer


def parse_diagnostic(value: str) -> Diagnostic:
    name, separator, result = value.partition("=")
    if not separator or not name:
        raise ValueError(f"invalid diagnostic: {value}")
    return Diagnostic(name=name, result=result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trusted PR release finalization orchestration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--base", required=True)
    prepare_parser.add_argument("--source", required=True)
    prepare_parser.add_argument("--source-pr", required=True, type=int)
    prepare_parser.add_argument("--commit", action="store_true")
    summary_parser = subparsers.add_parser("summarize")
    summary_parser.add_argument("--result", action="append", default=[])
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(base=args.base, source=args.source, source_pr=args.source_pr, commit=args.commit)
        return
    report = aggregate_diagnostics([parse_diagnostic(value) for value in args.result])
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["blocking"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
