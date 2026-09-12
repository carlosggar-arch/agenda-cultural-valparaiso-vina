"""Read-only routing of exact main pushes; never treats old certification as new.

The prior base's PR verifier/classifier, authenticated GitHub run metadata and
logs authorize the decision. Candidate-controlled classifications are not used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from release_decision import bind_source_decision


def require(value: bool, reason: str) -> None:
    if not value:
        raise SystemExit("PUBLICATION_RELEASE_DECISION_INVALID:" + reason)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def gh(*args: str):
    return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def require_exact_push(*, root: Path, candidate: str, before: str) -> None:
    for value in (candidate, before):
        require(re.fullmatch(r"[0-9a-f]{40}", value or "") is not None, "commit_identity")
    require(git(root, "rev-list", "--parents", "-n", "1", candidate).split() == [candidate, before], "exact_squash_parent")


def classify_push(*, root: Path, repository: str, candidate: str, before: str) -> dict:
    """A proven release only selects the full verifier, never grants publication."""
    require_exact_push(root=root, candidate=candidate, before=before)
    with tempfile.TemporaryDirectory(prefix="trusted-release-classifier-") as temporary:
        authority = Path(temporary)
        content = subprocess.check_output(["git", "show", f"{before}:app/scripts/ci_change_impact.py"], cwd=root)
        (authority / "ci_change_impact.py").write_bytes(content)
        output = subprocess.check_output(
            [sys.executable, "-I", "-S", str(authority / "ci_change_impact.py"),
             "--base", before, "--head", candidate], cwd=root, text=True)
    lines = output.splitlines()
    require(len(lines) == 5 and lines[0] == "CI_IMPACT", "classification_shape")
    fields = dict(line.split("=", 1) for line in lines[1:])
    require(set(fields) == {"product", "generated", "release", "changed_count"}, "classification_fields")
    require(all(fields[key] in {"true", "false"} for key in ("product", "generated", "release")), "classification_values")
    return bind_source_decision(root=root, repository=repository, impact={
        "release": fields["release"] == "true", "no_release": fields["release"] == "false",
        "source_base": before, "source_head": candidate, "authority_sha": before,
        "changed_count": int(fields["changed_count"]), "classification": fields,
    })


def verify_push_binding(*, root: Path, repository: str, candidate: str, before: str, pr: dict) -> str:
    require_exact_push(root=root, candidate=candidate, before=before)
    require(pr.get("merged") is True and pr.get("state") == "closed", "unmerged_pr")
    require(pr.get("merge_commit_sha") == candidate, "squash_commit")
    require(pr.get("base", {}).get("ref") == "main", "base_ref")
    for side in ("base", "head"):
        require(pr.get(side, {}).get("repo", {}).get("full_name") == repository, "repository")
    head = pr.get("head", {}).get("sha", "")
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "pr_head")
    require(git(root, "rev-parse", candidate + "^{tree}") == git(root, "rev-parse", head + "^{tree}"), "squash_tree")
    return head


def trusted_impact(*, root: Path, repository: str, before: str, head: str, pr: dict, run: dict, jobs: dict, log: str) -> dict:
    # Execute only prior-main tools in an isolated directory, never PR code.
    # Optional release_decision supports the first integration whose base predates it.
    with tempfile.TemporaryDirectory(prefix="trusted-release-decision-") as temporary:
        authority = Path(temporary)
        paths = ("pr_release_automation.py", "ci_change_impact.py", "release_finalizer.py",
                 "release_bundle.py", "core_publication_lineage.py", "generate_runtime_contracts.py")
        for name in (*paths, "release_decision.py"):
            object_name = f"{before}:app/scripts/{name}"
            content = subprocess.run(["git", "show", object_name], cwd=root, capture_output=True, check=False)
            if content.returncode:
                require(name == "release_decision.py", "authority_missing:" + name)
                continue
            (authority / name).write_bytes(content.stdout)
        for name, payload in (("run", run), ("jobs", jobs)):
            (authority / (name + ".json")).write_text(json.dumps(payload), encoding="utf-8")
        (authority / "source.log").write_text(log, encoding="utf-8")
        command = [sys.executable, "-I", "-S", str(authority / "pr_release_automation.py"), "verify-impact",
                   "--root", str(root), "--repository", repository, "--pr-number", str(pr["number"]),
                   "--run-id", str(run["id"]), "--run-attempt", str(run["run_attempt"]),
                   "--validated-head", head, "--current-head", head, "--current-base", before,
                   "--authority-sha", before, "--run-json", str(authority / "run.json"),
                   "--jobs-json", str(authority / "jobs.json"), "--log", str(authority / "source.log"),
                   "--github-output", str(authority / "output")]
        # -I omits the script directory. Use a fixed bootstrap to add only the
        # extracted authority directory; never cwd, PYTHONPATH or candidate code.
        command[3:4] = ["-c", "import sys,runpy; sys.path.insert(0,sys.argv[1]); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')", str(authority), str(authority / "pr_release_automation.py")]
        output = subprocess.check_output(command, cwd=authority, text=True)
        markers = [line.removeprefix("PR_FINALIZATION_IMPACT_VERIFIED ") for line in output.splitlines()
                   if line.startswith("PR_FINALIZATION_IMPACT_VERIFIED ")]
        require(len(markers) == 1, "authority_result")
        return bind_source_decision(root=root, repository=repository, impact=json.loads(markers[0]))


def resolve_push(*, root: Path, repository: str, candidate: str, before: str) -> dict:
    required = classify_push(root=root, repository=repository, candidate=candidate, before=before)
    associated = gh(f"repos/{repository}/commits/{candidate}/pulls")
    prs = [item for item in associated if item.get("merge_commit_sha") == candidate]
    if not associated and required["release"]:
        # The canonical Core App writes directly, then dispatches detached
        # lineage. Lack of a PR never proves no-release; the push still needs
        # every pre-existing full-release/lineage check before any mirror write.
        return {**required, "candidate_sha": candidate, "event": "push",
                "reason": "release-diff-requires-full-lineage"}
    require(len(prs) == 1, "merged_pr_count")
    pr = gh(f"repos/{repository}/pulls/{prs[0]['number']}")
    source_head = pr.get("head", {}).get("sha", "")
    require(re.fullmatch(r"[0-9a-f]{40}", source_head) is not None, "pr_head")
    if subprocess.run(["git", "cat-file", "-e", source_head + "^{commit}"], cwd=root,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        subprocess.check_call(["git", "fetch", "--no-tags", "origin", source_head], cwd=root)
    head = verify_push_binding(root=root, repository=repository, candidate=candidate, before=before, pr=pr)
    runs = gh(f"repos/{repository}/actions/workflows/pr-release.yml/runs?head_sha={head}&event=pull_request&per_page=100").get("workflow_runs", [])
    require(bool(runs), "source_gate_missing")
    # A later failed/pending run may not be hidden by an earlier successful one.
    latest = max(runs, key=lambda value: value["id"])
    run = gh(f"repos/{repository}/actions/runs/{latest['id']}/attempts/{latest['run_attempt']}")
    require(run.get("conclusion") == "success" and run.get("status") == "completed", "source_gate_not_successful")
    jobs = gh(f"repos/{repository}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100")
    guards = [job for job in jobs.get("jobs", []) if job.get("name") == "release-guard"]
    require(len(guards) == 1, "release_guard_count")
    log = subprocess.check_output(["gh", "run", "view", str(run["id"]), "--repo", repository,
                                   "--attempt", str(run["run_attempt"]), "--job", str(guards[0]["id"]), "--log"], text=True)
    decision = trusted_impact(root=root, repository=repository, before=before, head=head, pr=pr, run=run, jobs=jobs, log=log)
    require(decision["source_base"] == before, "source_base")
    require(decision["source_head"] == head, "source_head")
    require(decision["release"] == required["release"] and decision["diff_sha256"] == required["diff_sha256"], "push_diff_contradiction")
    return {**decision, "candidate_sha": candidate, "event": "push"}


DEPLOYMENT_STEPS = (
    "Create exact-tree handoff preserving deployment history",
    "Require exact deployment-branch parity with candidate",
    "Require release bump for runtime pushes",
    "Validate Cloudflare build snapshot and exact release lineage",
    "Push synchronized deployment branch",
    "Fast-close changed dataset freshness and identity",
    "Fast-close deterministic runtime contracts",
    "Wait once for both production origins in parallel",
    "Mark byte deployment, pending visual verification",
)


def require_no_release_outcome(*, repository: str, run: dict, jobs: dict, decision: dict, recomputed: dict) -> None:
    require(decision == recomputed and decision.get("no_release") is True, "routing_evidence_contradiction")
    require(run.get("event") == "push" and run.get("head_sha") == decision["candidate_sha"], "publication_run_identity")
    require(run.get("path") == ".github/workflows/publish.yml" and run.get("repository", {}).get("full_name") == repository,
            "publication_workflow_identity")
    require(run.get("status") == "completed" and run.get("conclusion") == "success", "publication_run_failed")
    def job(name):
        values = [value for value in jobs.get("jobs", []) if value.get("name") == name]
        require(len(values) == 1, "publication_job_count:" + name)
        value = values[0]
        require(value.get("run_id") == run["id"] and value.get("run_attempt") == run["run_attempt"]
                and value.get("head_sha") == run["head_sha"] and value.get("status") == "completed", "publication_job_identity")
        return value
    sync = job("sync-cloudflare")
    require(sync.get("conclusion") == "success", "routing_job_failed")
    for name in ("production-smoke", "refresh-open-release-prs"):
        require(job(name).get("conclusion") == "skipped", "unexpected_release_job:" + name)
    for name, expected in (
        *((name, "skipped") for name in DEPLOYMENT_STEPS),
        ("Verify exact release decision before deployment", "success"),
        ("Preserve verified deployment routing evidence", "success"),
        ("Verified no-release completes without deployment", "success"),
    ):
        steps = [step for step in sync.get("steps", []) if step.get("name") == name]
        require(len(steps) == 1 and steps[0].get("status") == "completed" and steps[0].get("conclusion") == expected,
                "unexpected_deployment_step:" + name)


def watchdog(*, root: Path, repository: str, run_id: int) -> bool:
    run = gh(f"repos/{repository}/actions/runs/{run_id}")
    jobs = gh(f"repos/{repository}/actions/runs/{run_id}/attempts/{run['run_attempt']}/jobs?per_page=100")
    smoke = [job for job in jobs.get("jobs", []) if job.get("name") == "production-smoke"]
    if len(smoke) != 1 or smoke[0].get("conclusion") != "skipped":
        return False  # Existing release/failed-release verification remains mandatory.
    candidate = run.get("head_sha", "")
    require(re.fullmatch(r"[0-9a-f]{40}", candidate) is not None, "publication_candidate")
    subprocess.check_call(["git", "fetch", "--no-tags", "origin", candidate], cwd=root)
    before = git(root, "rev-parse", candidate + "^")
    with tempfile.TemporaryDirectory(prefix="publication-routing-artifact-") as temporary:
        subprocess.check_call(["gh", "run", "download", str(run_id), "--repo", repository,
                               "--name", f"publication-release-decision-{run_id}-{run['run_attempt']}", "--dir", temporary])
        artifact = json.loads((Path(temporary) / "decision.json").read_text(encoding="utf-8"))
    recomputed = resolve_push(root=root, repository=repository, candidate=candidate, before=before)
    require_no_release_outcome(repository=repository, run=run, jobs=jobs, decision=artifact, recomputed=recomputed)
    print(f"PRODUCTION_NO_RELEASE_VERIFIED run={run_id} attempt={run['run_attempt']} head={candidate} deployed=false certified=false")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"), required=False)
    parser.add_argument("--event-name", choices=("push", "workflow_dispatch", "repository_dispatch"))
    parser.add_argument("--candidate")
    parser.add_argument("--watchdog-run", type=int)
    parser.add_argument("--before", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    require(bool(args.repository), "repository_missing")
    if args.watchdog_run:
        no_release = watchdog(root=args.root, repository=args.repository, run_id=args.watchdog_run)
        require(args.github_output is not None, "github_output_missing")
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write("no_release=" + str(no_release).lower() + "\n")
        return
    require(args.event_name is not None and args.candidate is not None and args.output is not None, "event_inputs_missing")
    if args.event_name == "push":
        decision = resolve_push(root=args.root, repository=args.repository, candidate=args.candidate, before=args.before)
    else:
        # Explicit publication events retain the complete lineage/certification
        # path. This cannot prove no-release or skip any release requirement.
        decision = {"contract": "verified-release-decision", "schema_version": 1,
                    "repository": args.repository, "candidate_sha": args.candidate,
                    "event": args.event_name, "release": True, "no_release": False,
                    "reason": "explicit-publication-requires-full-lineage"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write("release=" + str(decision["release"]).lower() + "\n")
    print("PUBLICATION_RELEASE_DECISION_VERIFIED " + json.dumps(decision, sort_keys=True))


if __name__ == "__main__":
    main()
