"""Coordinate existing publication jobs without granting unsigned authority."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil

import publication_execution_binding as binding
from publication_execution_github import GithubReader
import publication_release_decision as release_routing
from production_certification_history import validate_history, validated_core_execution
from verify_core_publication_bundle import verify_certificate_policy


def verified_bytes(root: Path, directory: Path) -> tuple[dict, str]:
    lineage = (directory / "attestation.json").read_bytes()
    receipt = (directory / "receipt.json").read_bytes()
    signed = (directory / "bundle.json").read_bytes()
    claim = binding.parse_json(lineage)
    # This does not replace verification. The preceding dedicated step ran gh;
    # retain its original result and require its authenticated certificate policy.
    verify_certificate_policy(binding.parse_json((directory / "verification.json").read_bytes()), claim)
    result = binding.binding_from_verified_bytes(
        lineage=lineage, receipt=receipt,
        release_bundle=(root / "app/data/release-bundle.json").read_bytes(), sigstore_bundle=signed)
    return result, claim["generated_at"]


def existing_certification(state_root: Path, expected: dict, canonical: dict | None = None) -> dict | None:
    history = validate_history(state_root)
    release = int(expected["release_id"].split("-", 1)[0].removeprefix("v"))
    rows = [row for row in history["certifications"] if row["head_sha"] == expected["public_sha"] and row["release"] == release]
    binding.require(len(rows) <= 1, "CERTIFICATION_AMBIGUOUS")
    if not rows:
        return None
    row = rows[0]
    record = binding.parse_json((state_root / row["path"]).read_bytes())
    index = validated_core_execution(record)
    binding.require(index is not None, "CERTIFICATION_CORE_AUTHORITY_MISSING")
    binding.validate_index(index, expected_binding=expected)
    if canonical is not None:
        binding.require(index["canonical"] == canonical, "CERTIFICATION_OWNER_MISMATCH")
    return {"index": index, "path": row["path"], "archive_sha256": row["archive_sha256"],
            "attestation_sha256": record["history_chain"]["attestation_sha256"]}


def check_visual_attestation(path: Path, *, expected_index: dict, expected_sha256: str) -> None:
    raw = path.read_bytes()
    binding.require(binding.sha256(raw) == expected_sha256, "VISUAL_ATTESTATION_BYTES_MISMATCH")
    actual = validated_core_execution(binding.parse_json(raw))
    binding.require(actual == binding.validate_index(expected_index), "VISUAL_ATTESTATION_EXECUTION_MISMATCH")


def prepare_core(*, root: Path, lineage_dir: Path, run_id: int, run_attempt: int,
                 workflow_head_sha: str, reader: GithubReader, state_root: Path) -> dict:
    # A distinct authenticated dispatch is an idempotent delivery. A rerun is
    # not: reconstructing prior attempts is outside this contract and cannot
    # silently create a replacement owner after a failed canonical execution.
    binding.require(run_attempt == 1, "UNSUPPORTED_RERUN_REQUIRES_ORIGINAL_EXECUTION")
    expected, not_before = verified_bytes(root, lineage_dir)
    expected_code = reader.code_hashes(expected["parent_sha"])
    binding.require(reader.code_hashes(expected["public_sha"]) == expected_code, "UNAUTHORISED_CANDIDATE_CODE")
    binding.require(expected_code == reader.code_hashes(workflow_head_sha),
                    "UNAUTHORISED_WORKFLOW_CODE")
    observations = reader.observations(expected, not_before, exclude_run=run_id)
    indices = [item["index"] for item in observations["verified"]]
    retained = existing_certification(state_root, expected)
    if retained is not None:
        binding.require(retained["index"] in indices, "RETAINED_EXECUTION_PROOF_MISSING")
    owner = binding.select_root(indices, expected_binding=expected)
    # Unknown prior attempts cannot be skipped to manufacture a new root.
    binding.require(not observations["pending"] and not observations["suspect"], "PRIOR_EXECUTION_UNPROVEN")
    if owner is None:
        current = reader.api(f"{reader.prefix}/git/ref/heads/main")
        binding.require((current.get("object") or {}).get("sha") == expected["public_sha"],
                        "STALE_UNCERTIFIED_CANDIDATE")
    index = binding.build_index(binding=expected, run_id=run_id, run_attempt=run_attempt,
                                workflow_head_sha=workflow_head_sha,
                                canonical=owner["canonical"] if owner else None)
    return {"action": "publish" if owner is None else "delegated", "core_execution": index,
            "retained_certification": retained, "not_before": not_before}


def ordinary_route(decision: dict) -> dict:
    binding.require(type(decision.get("release")) is bool and type(decision.get("no_release")) is bool
                    and decision["no_release"] is not decision["release"], "RELEASE_DECISION_INVALID")
    if decision["no_release"]:
        return {"action": "no_release"}
    if (decision.get("event") == "push"
            and decision.get("reason") == "release-diff-requires-full-lineage"):
        # Absence of a PR proves neither Core identity nor a valid publication.
        return {"action": "awaiting_authenticated_lineage", "authority": "unverified",
                "publication_state": "NOT_CERTIFIED", "deployed": False}
    return {"action": "publish"}


def require_non_deployment(run: dict, jobs: dict, *, action: str) -> None:
    sync = release_routing.exact_job(run, jobs, "sync-cloudflare")
    binding.require(run.get("status") == "completed" and run.get("conclusion") == "success"
                    and sync.get("status") == "completed" and sync.get("conclusion") == "success", "NON_DEPLOYMENT_RUN_INVALID")
    for name in release_routing.DEPLOYMENT_STEPS:
        release_routing.require_step(sync, name, "skipped")
    for name in ("production-smoke", "refresh-open-release-prs"):
        binding.require(release_routing.exact_job(run, jobs, name).get("conclusion") == "skipped", "UNEXPECTED_PUBLICATION_JOB")
    release_routing.require_step(sync, binding.EMIT_STEP)
    release_routing.require_step(sync, "Preserve verified deployment routing evidence")
    if action == "awaiting_authenticated_lineage":
        binding.require(run.get("event") == "push" and run.get("conclusion") == "success", "PRELIMINARY_RUN_INVALID")
        release_routing.require_step(sync, "Await authenticated publication authority without deployment")


def watchdog(*, root: Path, state_root: Path, run_id: int, reader: GithubReader) -> dict:
    run = reader.api(f"{reader.prefix}/actions/runs/{run_id}")
    jobs = {"jobs": reader.pages(f"{reader.prefix}/actions/runs/{run_id}/attempts/{run['run_attempt']}/jobs", "jobs")}
    if run.get("event") == "push":
        release_routing.require_run(run, repository=reader.repository, workflow="publish.yml", event="push", head=run.get("head_sha"))
        sync = release_routing.exact_job(run, jobs, "sync-cloudflare")
        waits = [step for step in sync.get("steps", []) if step.get("name") == "Await authenticated publication authority without deployment"]
        if waits and waits[0].get("conclusion") == "success":
            candidate = run["head_sha"]
            before = release_routing.git(root, "rev-parse", candidate + "^")
            decision = release_routing.resolve_push(root=root, repository=reader.repository, candidate=candidate, before=before)
            binding.require(ordinary_route(decision)["action"] == "awaiting_authenticated_lineage", "PRELIMINARY_ROUTING_CONTRADICTION")
            require_non_deployment(run, jobs, action="awaiting_authenticated_lineage")
            print(f"PUBLICATION_AUTHORITY_PENDING run={run_id} attempt={run['run_attempt']} head={candidate} state=NOT_CERTIFIED delegated=true")
            return {"no_release": False, "delegated": True, "effective_head": candidate}
        return {"no_release": release_routing.watchdog(root=root, repository=reader.repository, run_id=run_id), "delegated": False}
    if run.get("event") != "repository_dispatch":
        return {"no_release": False, "delegated": False}
    # Read only this run's public notice first. Metadata/code/step verification
    # below establishes it as an execution index, never as the Core signature.
    sync = release_routing.exact_job(run, jobs, "sync-cloudflare")
    endpoint = sync["check_run_url"].removeprefix("https://api.github.com/")
    annotations = reader.pages(endpoint + "/annotations")
    notices = [item for item in annotations if item.get("title") == binding.NOTICE_TITLE]
    binding.require(len(notices) == 1, "WATCHDOG_EXECUTION_NOTICE_MISSING")
    index = binding.parse_notice(notices[0]["message"])
    workflow = reader.api(f"{reader.prefix}/actions/workflows/publish.yml")
    expected_code = reader.code_hashes(index["binding"]["parent_sha"])
    binding.require(reader.code_hashes(index["binding"]["public_sha"]) == expected_code,
                    "UNAUTHORISED_CANDIDATE_CODE")
    binding.verify_github_index(index, run=run, job=sync, check_run=reader.api(endpoint), annotations=annotations,
                               expected_binding=index["binding"], workflow_id=workflow["id"],
                               expected_code_hashes=expected_code,
                               actual_code_hashes=reader.code_hashes(run["head_sha"]))
    if index["role"] == "delegated":
        require_non_deployment(run, jobs, action="delegated")
        retained = existing_certification(state_root, index["binding"], index["canonical"])
        binding.require(retained is not None, "DELEGATED_CERTIFICATION_MISSING")
        print(f"CORE_PUBLICATION_CERTIFICATION_REUSED run={run_id} canonical={index['canonical']['run_id']} head={index['binding']['public_sha']} writes=none")
        return {"no_release": False, "delegated": True, "effective_head": index["binding"]["public_sha"]}
    retained = existing_certification(state_root, index["binding"], index["canonical"])
    binding.require(retained is not None, "CANONICAL_CERTIFICATION_MISSING")
    return {"no_release": False, "delegated": False, "effective_head": index["binding"]["public_sha"],
            "execution_index": binding.encode_notice(index), "attestation_sha256": retained["attestation_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--lineage-dir", type=Path, default=Path("/tmp/core-publication-lineage"))
    parser.add_argument("--state-root", type=Path, default=Path(".production-certification-state"))
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/publication-release-decision"))
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--restore-index")
    parser.add_argument("--watchdog-run", type=int)
    parser.add_argument("--check-attestation", type=Path)
    parser.add_argument("--expected-index")
    parser.add_argument("--expected-attestation-sha")
    args = parser.parse_args()
    if args.check_attestation is not None:
        check_visual_attestation(args.check_attestation, expected_index=binding.parse_notice(args.expected_index),
                                 expected_sha256=args.expected_attestation_sha)
        return
    if args.watchdog_run is not None:
        result = watchdog(root=args.root, state_root=args.state_root, run_id=args.watchdog_run, reader=GithubReader(args.root))
    elif args.restore_index is not None:
        expected, _ = verified_bytes(args.root, args.lineage_dir)
        index = binding.validate_index(binding.parse_notice(args.restore_index), expected_binding=expected)
        binding.require(index["role"] == "canonical" and index["execution"]["workflow_head_sha"] == os.environ["GITHUB_SHA"]
                        and binding.run_key(index["execution"]) ==
                        (int(os.environ["GITHUB_RUN_ID"]), int(os.environ["GITHUB_RUN_ATTEMPT"])), "RESTORED_EXECUTION_INVALID")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "core-execution.json").write_bytes(binding.canonical_bytes(index) + b"\n")
        return
    else:
        decision = binding.parse_json(args.decision.read_bytes())
        ordinary = ordinary_route(decision)
        if decision.get("event") == "repository_dispatch":
            binding.require(decision["release"] is True, "CORE_RELEASE_DECISION_CONTRADICTION")
            result = prepare_core(root=args.root, lineage_dir=args.lineage_dir,
                                  run_id=int(os.environ["GITHUB_RUN_ID"]), run_attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
                                  workflow_head_sha=os.environ["GITHUB_SHA"], reader=GithubReader(args.root), state_root=args.state_root)
        else:
            result = ordinary
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "execution-route.json").write_bytes(binding.canonical_bytes(result) + b"\n")
        if "core_execution" in result:
            index = result["core_execution"]
            shutil.copytree(args.lineage_dir, args.output_dir / "core-publication-lineage", dirs_exist_ok=False)
            (args.output_dir / "core-execution.json").write_bytes(binding.canonical_bytes(index) + b"\n")
            encoded = binding.encode_notice(index)
            print(f"::notice file={binding.WORKFLOW},line=1,title={binding.NOTICE_TITLE}::{encoded}")
            result = {**result, "execution_index": encoded}
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            for key in ("action", "execution_index", "no_release", "delegated", "effective_head", "attestation_sha256"):
                if key in result:
                    value = str(result[key]).lower() if type(result[key]) is bool else result[key]
                    stream.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
