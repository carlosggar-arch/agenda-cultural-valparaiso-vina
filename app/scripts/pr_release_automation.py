from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import release_finalizer
import ci_change_impact
from release_decision import bind_source_decision


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
        "app/scripts/ci_change_impact.py",
        "app/scripts/core_publication_lineage.py",
        "app/scripts/pr_release_automation.py",
        "app/scripts/release_decision.py",
        "app/scripts/publication_release_decision.py",
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


def verify_source_impact(
    *, root: Path, repository: str, pr_number: int, run_id: int, run_attempt: int,
    validated_head: str, current_head: str, current_base: str, authority_sha: str,
    run: dict, jobs: dict, log: str,
) -> dict[str, object]:
    """Recompute a run's exact diff using trusted tools, without PR execution/writes.

    The existing gate logs its fetched integration base and classification. Neither
    an absent handoff nor a boolean supplied by PR code is sufficient authority.
    This function must be loaded from main, along with ci_change_impact.py.
    """
    def require(condition: bool, reason: str) -> None:
        if not condition:
            raise SystemExit("PR_FINALIZATION_IMPACT_INVALID:" + reason)

    def read_git(*args: str) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError as exc:
            raise SystemExit("PR_FINALIZATION_IMPACT_INVALID:unverifiable_git_evidence") from exc

    def only(values: list, reason: str):
        require(len(values) == 1, reason)
        return values[0]

    for value in (validated_head, current_head, current_base, authority_sha):
        require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None, "sha")
    require(authority_sha == current_base, "authority_base_moved")
    require(run.get("id") == run_id and type(run.get("id")) is int, "run_id")
    require(run.get("run_attempt") == run_attempt and type(run.get("run_attempt")) is int, "run_attempt")
    require(run.get("name") == "PR release gate", "workflow_name")
    require(run.get("path") == ".github/workflows/pr-release.yml", "workflow_path")
    require(run.get("event") == "pull_request" and run.get("status") == "completed", "run_state")
    require(run.get("repository", {}).get("full_name") == repository, "repository")
    require(run.get("head_repository", {}).get("full_name") == repository, "head_repository")
    require(run.get("head_sha") == validated_head, "run_head")
    source_pr = only(run.get("pull_requests", []), "source_pr_count")
    require(source_pr.get("number") == pr_number and type(source_pr.get("number")) is int, "pr_number")
    require(source_pr.get("head", {}).get("sha") == validated_head, "pr_head")
    require(source_pr.get("base", {}).get("ref") == "main", "base_ref")
    require(source_pr.get("head", {}).get("repo", {}).get("id") == source_pr.get("base", {}).get("repo", {}).get("id")
            and type(source_pr.get("head", {}).get("repo", {}).get("id")) is int, "fork")

    job = only([item for item in jobs.get("jobs", []) if item.get("name") == "release-guard"], "release_job_count")
    require(job.get("run_id") == run_id and job.get("run_attempt") == run_attempt, "job_run")
    require(job.get("head_sha") == validated_head and job.get("status") == "completed", "job_head_state")
    steps = job.get("steps", [])
    def step_result(name: str) -> str:
        step = only([item for item in steps if item.get("name") == name], "step:" + name)
        require(step.get("status") == "completed", "step_state:" + name)
        return step.get("conclusion", "")

    require(step_result("Fetch current integration base") == "success", "queue_failed")
    require(step_result("Classify release impact against current main") == "success", "classification_failed")
    # gh job logs may lack step labels (UNKNOWN STEP); use only exact timestamped
    # payloads, never echoed shell commands. Duplicate/ambiguous markers fail closed.
    payloads = []
    for line in log.splitlines():
        fields = line.split("\t", 2)
        require(len(fields) == 3 and fields[0] == job["name"], "log_job")
        match = re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z ?(.*)", fields[2].removeprefix("\ufeff"))
        require(match is not None, "log_timestamp")
        payloads.append(match.group(1))
    source_base = only([line.removeprefix("RELEASE_QUEUE_BASE=") for line in payloads
                        if line.startswith("RELEASE_QUEUE_BASE=")], "queue_base_count")
    require(re.fullmatch(r"[0-9a-f]{40}", source_base) is not None, "queue_base_sha")
    candidate = only([line.removeprefix("RELEASE_QUEUE_CANDIDATE=") for line in payloads
                      if line.startswith("RELEASE_QUEUE_CANDIDATE=")], "queue_head_count")
    require(candidate == validated_head, "queue_head")
    position = only([index for index, line in enumerate(payloads) if line == "CI_IMPACT"], "classification_count")
    classification = payloads[position + 1:position + 5]
    require(len(classification) == 4, "classification_missing")
    declared: dict[str, object] = {}
    for key, line in zip(("product", "generated", "release", "changed_count"), classification):
        name, separator, value = line.partition("=")
        require(separator == "=" and name == key, "classification_field")
        if key == "changed_count":
            require(re.fullmatch(r"0|[1-9][0-9]*", value) is not None, "classification_count_type")
            declared[key] = int(value)
        else:
            require(value in {"true", "false"}, "classification_boolean")
            declared[key] = value == "true"

    for sha in (source_base, validated_head, authority_sha):
        require(read_git("rev-parse", "--verify", sha + "^{commit}") == sha, "unverifiable_commit")
    # The logs' meaning must come from the same workflow and classifier as the
    # trusted authority, not from a PR changing how those markers are produced.
    for path in (".github/workflows/pr-release.yml", "app/scripts/ci_change_impact.py"):
        require(read_git("rev-parse", validated_head + ":" + path) ==
                read_git("rev-parse", authority_sha + ":" + path), "untrusted_classification_code:" + path)
    paths = [path for path in read_git("diff", "--name-only", source_base + "..." + validated_head).splitlines() if path]
    recomputed = ci_change_impact.classify(paths)
    require(set(recomputed) == {"product", "generated", "release"}
            and all(type(value) is bool for value in recomputed.values()), "unknown_classification")
    require(declared == {**recomputed, "changed_count": len(paths)}, "classification_contradiction")
    release = recomputed["release"]
    require(step_result("No release surface affected") == ("skipped" if release else "success"), "classification_step_contradiction")
    if not release:
        require(current_head == validated_head, "current_head_moved")
        require(current_base == source_base, "current_base_moved")
        require(run.get("conclusion") == "success" and job.get("conclusion") == "success", "validation_failed")
        require(step_result("Run independent release diagnostics and aggregate failures") == "success", "diagnostics_failed")
        require(step_result("Publish one aggregate diagnostic summary") == "success", "summary_failed")
        require(step_result("Require or transiently prepare canonical finalization") == "skipped", "unexpected_finalization")
        require(subprocess.run(["git", "merge-base", "--is-ancestor", source_base, validated_head],
                               cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
                "base_not_ancestor")
    # release=true still goes through the existing refresh, full handoff and
    # finalizer checks. A pending source-finalizer gate is not a no-release proof.
    return bind_source_decision(root=root, repository=repository, impact={
        "release": release, "no_release": not release, "source_base": source_base,
        "source_head": validated_head, "authority_sha": authority_sha,
        "run_id": run_id, "run_attempt": run_attempt, "pr": pr_number,
        "changed_count": len(paths),
        "paths_sha256": hashlib.sha256(json.dumps(sorted(paths), ensure_ascii=True, separators=(",", ":")).encode()).hexdigest(),
    })


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_check(*args: str) -> bool:
    return subprocess.run(
        ["git", *args], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0


def changed_paths(base: str, head: str) -> set[str]:
    output = git("diff", "--name-only", f"{base}...{head}")
    return {line for line in output.splitlines() if line}


def status_paths(root: Path = ROOT) -> set[str]:
    """Return exact paths from porcelain status without trimming its XY prefix."""
    output = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=root
    )
    records = output.split(b"\0")
    paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            raise SystemExit("PR_FINALIZATION_INVALID_GIT_STATUS")
        status = record[:2]
        paths.add(record[3:].decode("utf-8", errors="surrogateescape"))
        if b"R" in status or b"C" in status:
            if index >= len(records) or not records[index]:
                raise SystemExit("PR_FINALIZATION_INVALID_GIT_STATUS_RENAME")
            index += 1  # The source path is informational; the destination is authoritative.
    return paths


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
    generated = status_paths()
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
    impact_parser = subparsers.add_parser("verify-impact")
    impact_parser.add_argument("--root", required=True, type=Path)
    impact_parser.add_argument("--repository", required=True)
    impact_parser.add_argument("--pr-number", required=True, type=int)
    impact_parser.add_argument("--run-id", required=True, type=int)
    impact_parser.add_argument("--run-attempt", required=True, type=int)
    for name in ("validated-head", "current-head", "current-base", "authority-sha"):
        impact_parser.add_argument("--" + name, required=True)
    for name in ("run-json", "jobs-json", "log", "github-output"):
        impact_parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(base=args.base, source=args.source, source_pr=args.source_pr, commit=args.commit)
        return
    if args.command == "verify-impact":
        result = verify_source_impact(
            root=args.root, repository=args.repository, pr_number=args.pr_number,
            run_id=args.run_id, run_attempt=args.run_attempt,
            validated_head=args.validated_head, current_head=args.current_head,
            current_base=args.current_base, authority_sha=args.authority_sha,
            run=json.loads(args.run_json.read_text(encoding="utf-8")),
            jobs=json.loads(args.jobs_json.read_text(encoding="utf-8")),
            log=args.log.read_text(encoding="utf-8"),
        )
        print("PR_FINALIZATION_IMPACT_VERIFIED " + json.dumps(result, sort_keys=True))
        with args.github_output.open("a", encoding="utf-8") as handle:
            for key in ("release", "no_release"):
                handle.write(f"{key}={str(result[key]).lower()}\n")
        return
    report = aggregate_diagnostics([parse_diagnostic(value) for value in args.result])
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["blocking"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
