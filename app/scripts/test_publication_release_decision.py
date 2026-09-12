"""Real Git + trusted-base tools; only the GitHub transport is a fixture.

No deployment, certification, cultural source or publication is executed.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import ci_change_impact
import publication_release_decision as routing
import pr_release_automation
import release_finalizer


ROOT = Path(__file__).resolve().parents[2]


def reject(call, marker="INVALID"):
    try:
        call()
    except (SystemExit, subprocess.CalledProcessError) as exc:
        if isinstance(exc, SystemExit):
            assert marker in str(exc), str(exc)
    else:
        raise AssertionError("unverifiable routing accepted")


def run_git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def test_event_routing():
    repository = "example/agenda"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        run_git(root, "init", "-q")
        run_git(root, "config", "user.name", "Routing fixture")
        run_git(root, "config", "user.email", "routing@example.invalid")
        run_git(root, "config", "core.autocrlf", "false")
        for name in ("pr_release_automation.py", "release_decision.py", "ci_change_impact.py", "release_finalizer.py",
                     "release_bundle.py", "core_publication_lineage.py", "generate_runtime_contracts.py"):
            path = root / "app/scripts" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / "app/scripts" / name).read_bytes())
        for name in ("pr-release.yml", "publish.yml"):
            path = root / ".github/workflows" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / ".github/workflows" / name).read_bytes())
        run_git(root, "add", ".")
        run_git(root, "commit", "-qm", "Trusted fixture base")
        base = run_git(root, "rev-parse", "HEAD")
        for is_release in (False, True):
            run_git(root, "checkout", "--detach", "-q", base)
            # Exactly the triggering workflow edit plus an optional real release surface.
            (root / ".github/workflows/publish.yml").write_text("# fixture workflow edit\n", encoding="utf-8")
            if is_release:
                (root / "app/app.js").write_text("export const RELEASE_FIXTURE = true;\n", encoding="utf-8")
            run_git(root, "add", ".")
            run_git(root, "commit", "-qm", "Fixture source, no privileged marker")
            head = run_git(root, "rev-parse", "HEAD")
            # An actual distinct squash object, not ancestry or a commit-message heuristic.
            candidate = subprocess.check_output(
                ["git", "commit-tree", head + "^{tree}", "-p", base], cwd=root,
                input="Fixture protected squash\n", text=True).strip()
            paths = run_git(root, "diff", "--name-only", base, head).splitlines()
            impact = ci_change_impact.classify(paths)
            assert impact["release"] is is_release
            pr = {"number": 23, "merged": True, "state": "closed", "merge_commit_sha": candidate,
                  "head": {"sha": head, "repo": {"full_name": repository, "id": 31}},
                  "base": {"ref": "main", "repo": {"full_name": repository, "id": 31}}}
            run = {"id": 101, "run_attempt": 1, "name": "PR release gate", "path": ".github/workflows/pr-release.yml",
                   "run_started_at": "2026-09-12T12:00:00Z",
                   "event": "pull_request", "head_sha": head, "status": "completed", "conclusion": "success",
                   "repository": {"full_name": repository}, "head_repository": {"full_name": repository},
                   "pull_requests": [{"number": 23, "head": pr["head"], "base": pr["base"]}]}
            steps = [{"name": name, "status": "completed", "conclusion": result} for name, result in (
                ("Fetch current integration base", "success"), ("Classify release impact against current main", "success"),
                ("Run independent release diagnostics and aggregate failures", "success"),
                ("Require or transiently prepare canonical finalization", "success" if is_release else "skipped"),
                ("No release surface affected", "skipped" if is_release else "success"),
                ("Publish one aggregate diagnostic summary", "success"))]
            jobs = {"jobs": [{"id": 201, "run_id": 101, "run_attempt": 1, "name": "release-guard",
                              "head_sha": head, "status": "completed", "conclusion": "success", "steps": steps}]}
            payloads = [f"RELEASE_QUEUE_BASE={base}", f"RELEASE_QUEUE_CANDIDATE={head}", "CI_IMPACT",
                        *[f"{key}={str(value).lower()}" for key, value in impact.items()], f"changed_count={len(paths)}"]
            log = "\n".join(f"release-guard\tUNKNOWN STEP\t2026-09-12T12:00:00.123Z {line}" for line in payloads)
            responses = {
                f"repos/{repository}/commits/{candidate}/pulls": [pr], f"repos/{repository}/pulls/23": pr,
                f"repos/{repository}/actions/workflows/pr-release.yml/runs?head_sha={head}&event=pull_request&per_page=100": {"workflow_runs": [run], "total_count": 1},
                f"repos/{repository}/actions/runs/101": run,
                f"repos/{repository}/actions/runs/101/attempts/1/jobs?per_page=100": jobs,
            }
            real_check_output = subprocess.check_output
            final_logs = {}
            def transport(command, *args, **kwargs):
                if command[0] == "gh":
                    if command[3] in final_logs:
                        assert command == ["gh", "run", "view", command[3], "--repo", repository,
                                           "--attempt", str(responses[f"repos/{repository}/actions/runs/{command[3]}"]["run_attempt"]),
                                           "--job", "601", "--log"], command
                        return final_logs[command[3]]
                    assert command == ["gh", "run", "view", "101", "--repo", repository,
                                       "--attempt", "1", "--job", "201", "--log"], command
                    return log
                return real_check_output(command, *args, **kwargs)
            with patch.object(routing, "gh", side_effect=lambda endpoint, *flags: deepcopy([responses[endpoint]] if flags else responses[endpoint])), \
                 patch.object(routing.subprocess, "check_output", side_effect=transport):
                args = dict(root=root, repository=repository, candidate=candidate, before=base)
                decision = routing.resolve_push(**args)
                pr_decision = pr_release_automation.verify_source_impact(
                    root=root, repository=repository, pr_number=23, run_id=101, run_attempt=1,
                    validated_head=head, current_head=head, current_base=base, authority_sha=base,
                    run=run, jobs=jobs, log=log)
                assert decision == {**pr_decision, "candidate_sha": candidate, "event": "push"}
                assert decision["release"] is is_release and decision["schema_version"] == 1
                assert decision["candidate_sha"] == candidate and decision["source_head"] == head
                assert routing.resolve_push(**args) == decision
                assert len(decision["diff_sha256"]) == 64
                # Wrong HEAD/base/PR, missing logs, contradictory classification and failed gate cannot route.
                reject(lambda: routing.resolve_push(**dict(args, before=head)))
                original_log = log
                log = ""
                reject(lambda: routing.resolve_push(**args))
                log = original_log.replace(f"release={str(is_release).lower()}", f"release={str(not is_release).lower()}")
                reject(lambda: routing.resolve_push(**args))
                log = original_log
                run["conclusion"] = "failure"
                reject(lambda: routing.resolve_push(**args))
                run["conclusion"] = "success"
                pr["merge_commit_sha"] = head
                reject(lambda: routing.resolve_push(**args))
                pr["merge_commit_sha"] = candidate
                associated_path = f"repos/{repository}/commits/{candidate}/pulls"
                responses[associated_path] = []
                if is_release:
                    direct = routing.resolve_push(**args)
                    assert direct["release"] is True and direct["no_release"] is False
                    assert direct["reason"] == "release-diff-requires-full-lineage"
                else:
                    reject(lambda: routing.resolve_push(**args))
                responses[associated_path] = [pr]
                # GitHub's captured post-merge shape is pull_requests=[]. The
                # following authority v1 is a LOCAL fixture, not a remote run.
                run["pull_requests"] = []
                final = {"id": 501, "run_attempt": 1, "run_started_at": "2026-09-12T12:01:00Z",
                         "name": "Finalize validated PR candidate", "path": ".github/workflows/pr-finalize.yml",
                         "event": "workflow_run", "head_sha": base, "status": "completed", "conclusion": "success",
                         "repository": {"full_name": repository}, "head_repository": {"full_name": repository}}
                final_step_names = ["Checkout trusted automation authority", "Capture trusted finalization tools",
                                    "Resolve immutable PR snapshot", "Verify release impact from trusted authority"]
                final_steps = [{"name": name, "status": "completed", "conclusion": "success"} for name in final_step_names]
                if not is_release:
                    final_steps.append({"name": "Validated no-release candidate needs no finalizer", "status": "completed", "conclusion": "success"})
                    final_steps += [{"name": name, "status": "completed", "conclusion": "skipped"} for name in
                        ("Mint narrowly scoped PR finalizer token", "Refresh safely when main advanced",
                         "Verify successful source-validation handoff", "Prepare exact finalizer commit without credentials",
                         "Revalidate immutable head and base", "Fast-forward the PR branch to the validated finalizer")]
                final_jobs = {"jobs": [{"id": 601, "run_id": 501, "run_attempt": 1, "head_sha": base,
                                       "name": "finalize-validated-pr", "status": "completed", "conclusion": "success", "steps": final_steps}]}
                final_list = f"repos/{repository}/actions/workflows/pr-finalize.yml/runs?head_sha={base}&event=workflow_run&per_page=100"
                responses[final_list] = {"total_count": 1, "workflow_runs": [final]}
                responses[f"repos/{repository}/actions/runs/501"] = final
                responses[f"repos/{repository}/actions/runs/501/attempts/1/jobs?per_page=100"] = final_jobs
                env = {"PR_NUMBER": "23", "VALIDATED_HEAD": head, "HEAD_SHA": head, "BASE_SHA": base,
                       "AUTHORITY_SHA": base, "RUN_ID": "101", "RUN_ATTEMPT": "1"}
                def authority_log(proof=pr_decision, *, values=env):
                    payloads = [f"  {key}: {value}" for key, value in values.items()]
                    if proof is not None:
                        payloads.append("PR_FINALIZATION_IMPACT_VERIFIED " + json.dumps(proof))
                    return "\n".join(f"finalize-validated-pr\tUNKNOWN STEP\t2026-09-12T12:01:01Z {line}" for line in payloads)
                final_logs["501"] = authority_log()
                immutable = deepcopy(run)
                assert routing.resolve_push(**args) == decision
                assert run == immutable, "Never rehydrate or replace the original empty association"
                assert routing.resolve_push(**args) == decision
                for key, bad in (("schema_version", True), ("schema_version", 0), ("diff_sha256", "0" * 64),
                                 ("source_head", base), ("source_base", head), ("authority_sha", head),
                                 ("repository", "other/repo"), ("pr", 24), ("run_id", 102), ("run_attempt", 2),
                                 ("release", not is_release), ("no_release", is_release)):
                    bad_proof = deepcopy(pr_decision)
                    bad_proof[key] = bad
                    final_logs["501"] = authority_log(bad_proof)
                    reject(lambda: routing.resolve_push(**args))
                legacy = {key: value for key, value in pr_decision.items() if key not in ("contract", "schema_version", "repository", "diff_sha256")}
                for bad_log in (authority_log(None), authority_log(legacy), authority_log() + "\n" + authority_log(),
                                authority_log() + "\nfinalize-validated-pr\tUNKNOWN STEP\t2026-09-12T12:01:01Z   RUN_ID: 999"):
                    final_logs["501"] = bad_log
                    reject(lambda: routing.resolve_push(**args))
                final_logs["501"] = authority_log()
                for key, bad in (("path", ".github/workflows/other.yml"), ("event", "pull_request"),
                                 ("head_sha", head), ("repository", {"full_name": "other/repo"}), ("conclusion", "failure")):
                    previous = final[key]
                    final[key] = bad
                    reject(lambda: routing.resolve_push(**args))
                    final[key] = previous
                final_jobs["jobs"][0]["run_attempt"] = 2
                reject(lambda: routing.resolve_push(**args))
                final_jobs["jobs"][0]["run_attempt"] = 1
                for step in final_steps:
                    old = step["conclusion"]
                    step["conclusion"] = "failure"
                    reject(lambda: routing.resolve_push(**args))
                    step["conclusion"] = old
                # A rerun of a LOWER id can be the newest attempt. Its failure
                # and absence of proof must not disappear behind id=501 success.
                later = dict(final, id=499, run_attempt=2, run_started_at="2026-09-12T12:02:00Z", conclusion="failure")
                later_jobs = deepcopy(final_jobs)
                later_jobs["jobs"][0].update(run_id=499, run_attempt=2, conclusion="failure")
                responses[final_list] = {"total_count": 2, "workflow_runs": [final, later]}
                responses[f"repos/{repository}/actions/runs/499"] = later
                responses[f"repos/{repository}/actions/runs/499/attempts/2/jobs?per_page=100"] = later_jobs
                final_logs["499"] = authority_log(None)
                reject(lambda: routing.resolve_push(**args), "latest_finalizer_failed")
                responses[final_list] = {"total_count": 1, "workflow_runs": [final]}
                source_list = f"repos/{repository}/actions/workflows/pr-release.yml/runs?head_sha={head}&event=pull_request&per_page=100"
                later_source = dict(run, id=99, run_attempt=2, run_started_at="2026-09-12T12:03:00Z", conclusion="failure")
                responses[source_list] = {"total_count": 2, "workflow_runs": [run, later_source]}
                responses[f"repos/{repository}/actions/runs/99"] = later_source
                reject(lambda: routing.resolve_push(**args), "source_gate_not_successful")
                responses[source_list] = {"total_count": 1, "workflow_runs": [run]}
                responses[f"repos/{repository}/actions/runs/101"] = dict(run, run_attempt=2, run_started_at="2026-09-12T12:04:00Z")
                reject(lambda: routing.resolve_push(**args), "source_attempt_moved")
                responses[f"repos/{repository}/actions/runs/101"] = run
                for value in (None, {}, "", [dict(number=999, head={"sha": head})]):
                    run["pull_requests"] = value
                    reject(lambda: routing.resolve_push(**args))
                run.pop("pull_requests")
                reject(lambda: routing.resolve_push(**args))
                run["pull_requests"] = []
                responses[final_list]["total_count"] = 101
                reject(lambda: routing.resolve_push(**args), "run_pages_incomplete")
                responses[final_list]["total_count"] = 1
            assert run_git(root, "status", "--porcelain") == ""
            assert not (root / "handoff.json").exists()
            assert not (root / "app/data/release-provenance.json").exists()
            if not is_release:
                publication = {"id": 401, "run_attempt": 1, "head_sha": candidate, "status": "completed",
                               "conclusion": "success", "event": "push", "repository": {"full_name": repository},
                               "path": ".github/workflows/publish.yml"}
                pubjobs = {"jobs": [{"name": name, "run_id": 401, "run_attempt": 1, "head_sha": candidate,
                                     "status": "completed", "conclusion": result} for name, result in
                                    (("sync-cloudflare", "success"), ("production-smoke", "skipped"), ("refresh-open-release-prs", "skipped"))]}
                pubjobs["jobs"][0]["steps"] = [{"name": name, "status": "completed", "conclusion": result} for name, result in
                    (*((name, "skipped") for name in routing.DEPLOYMENT_STEPS),
                     ("Verify exact release decision before deployment", "success"),
                     ("Preserve verified deployment routing evidence", "success"),
                     ("Verified no-release completes without deployment", "success"))]
                outcome = dict(repository=repository, run=publication, jobs=pubjobs, decision=decision, recomputed=decision)
                routing.require_no_release_outcome(**outcome)
                changed = deepcopy(decision)
                changed["candidate_sha"] = head
                reject(lambda: routing.require_no_release_outcome(**dict(outcome, decision=changed)))
                changed = deepcopy(decision)
                changed["diff_sha256"] = "0" * 64
                reject(lambda: routing.require_no_release_outcome(**dict(outcome, decision=changed)))
                for job in pubjobs["jobs"]:
                    old = job["conclusion"]
                    job["conclusion"] = "failure" if old == "success" else "success"
                    reject(lambda: routing.require_no_release_outcome(**outcome))
                    job["conclusion"] = old
                for step in pubjobs["jobs"][0]["steps"]:
                    old = step["conclusion"]
                    step["conclusion"] = "success" if old == "skipped" else "skipped"
                    reject(lambda: routing.require_no_release_outcome(**outcome))
                    step["conclusion"] = old
            else:
                # New routing does not grant release lineage, and the old certificate still rejects another SHA.
                evidence = {"number": 23, "state": "MERGED", "mergeCommit": {"oid": base}}
                reject(lambda: release_finalizer.validate_squash_pr_evidence(
                    evidence, source_pr=23, published_sha=candidate, published_tree=run_git(root, "rev-parse", candidate + "^{tree}")),
                    "PUBLISHED_SQUASH_MERGE_COMMIT_MISMATCH")


def test_workflow_path():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert '      - ".github/workflows/publish.yml"' in workflow.split("permissions:")[0]
    for name in ("publication_release_decision.py", "release_decision.py"):
        assert f'      - "app/scripts/{name}"' in workflow.split("permissions:")[0]
    sync = workflow.split("  sync-cloudflare:", 1)[1].split("  production-smoke:", 1)[0]
    assert sync.index("Verify exact release decision before deployment") < sync.index(routing.DEPLOYMENT_STEPS[0])
    for name in routing.DEPLOYMENT_STEPS:
        block = sync.split("- name: " + name, 1)[1].split("- name:", 1)[0]
        assert "if: steps.release-decision.outputs.release == 'true'" in block, name
    assert "if: needs.sync-cloudflare.outputs.release == 'true'" in workflow
    assert "    needs: production-smoke" in workflow.split("  refresh-open-release-prs:", 1)[1]
    assert workflow.count('release_finalizer.py --check-published --finalizer-ref "$CANDIDATE_SHA"') == 2
    assert "production_release_attestation.py" in workflow and "production_release_chain.py" in workflow
    assert "Push synchronized deployment branch" in workflow and "Persist immutable production certification" in workflow
    assert "workflows: [\"Publish and production verification\"]" in (ROOT / ".github/workflows/production-certification-watchdog.yml").read_text(encoding="utf-8")
    fast = (ROOT / ".github/workflows/pr-fast.yml").read_text(encoding="utf-8")
    assert "python app/scripts/test_pr_finalization_workflow.py" in fast
    official = (ROOT / "app/scripts/test_pr_finalization_workflow.py").read_text(encoding="utf-8")
    assert "from test_publication_release_decision import main as routing_contract" in official
    assert "    routing_contract()" in official


def main():
    test_event_routing()
    test_workflow_path()
    print("PUBLICATION_RELEASE_DECISION_TESTS_OK event=publish-workflow-push authority=prior-base no_release=no-writes release=full-lineage watchdog=recomputed negatives=closed")


if __name__ == "__main__":
    main()
