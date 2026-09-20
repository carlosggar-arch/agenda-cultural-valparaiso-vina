"""A later verification of an immutable publication, never a new owner.

Pure shared contract. A proof is not a signature: callers must authenticate
the historical Core bundle AND both executions against GitHub metadata.
"""
from __future__ import annotations

import base64
import re
from pathlib import PurePosixPath
from typing import Any, Mapping

try:
    from . import publication_execution_binding as original
except ImportError:
    import publication_execution_binding as original

CONTRACT = "core-publication-snapshot-verification"
VERSION = "2.0.0"
WORKFLOW = ".github/workflows/publish.yml"
VERIFY_JOB = "verify-snapshot"
SMOKE_JOB = "snapshot-production-smoke"
VERIFY_STEP = "Verify original publication evidence"
EMIT_STEP = "Bind exact snapshot verification"
NOTICE_TITLE = "SNAPSHOT_PUBLICATION_VERIFICATION_V1"
NOTICE_CONTRACT = "core-publication-snapshot-verification-index"
NOTICE_VERSION = "2.0.0"
WATCHDOG_WORKFLOW = ".github/workflows/production-certification-watchdog.yml"
WATCHDOG_JOB = "certification-watchdog"
WATCHDOG_STEP = "Verify exact snapshot certification"
WATCHDOG_NOTICE = "SNAPSHOT_PUBLICATION_WATCHDOG_V1"
NON_PUBLIC_VERIFICATION_PREFIXES = (".github/", "app/scripts/", "docs/", "tests/", "scripts/")
NON_PUBLIC_VERIFICATION_FILES = frozenset({"AGENTS.md", "requirements-ci.txt"})
# Snapshot-verification v2 is a frozen historical authority.  The newer
# post-write recovery helper is authenticated by its own runtime policy; adding
# it retroactively here would invalidate the already approved v2 tree.
SNAPSHOT_EXECUTION_CODE_PATHS = tuple(
    path for path in original.CODE_PATHS
    if path != "app/scripts/post_write_recovery_authority.py"
)
CODE_PATHS = tuple(dict.fromkeys((*SNAPSHOT_EXECUTION_CODE_PATHS,
    "app/scripts/publication_snapshot_verification.py",
    "app/scripts/snapshot_verification_cli.py",
    "app/scripts/snapshot_production_smoke.py",
    "app/scripts/deployment_readiness.py",
    "app/scripts/production_pwa_smoke.py",
    "app/scripts/production_browser_selenium_smoke.py",
    "app/scripts/production_warm_start_smoke.py",
    "app/scripts/production_admin_staging_smoke.py",
    "app/scripts/production_series_contract.py",
    "app/scripts/test_web_pwa_visibility_parity.py",
    "app/scripts/production_certification_watchdog.py",
    "app/scripts/release_bundle.py",
    "app/scripts/generate_runtime_contracts.py",
    "requirements-ci.txt",
)))
PRESERVED_SURFACES = (
    "agenda_web.json",
    "app/data/gijon/agenda_web.json",
    "fuentes_publicas.json",
    "app/data/source-registry.json",
    "app/data/quality/source-coverage.json",
    "app/data/quality/event-quality.json",
    "app/data/quality/release-readiness.json",
    "app/data/venue-registry.json",
)
FIELDS = {
    "contract", "version", "original_core_execution", "execution", "verifier",
    "original_artifact", "composition",
}


class SnapshotVerificationError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise SnapshotVerificationError("SNAPSHOT_VERIFICATION_" + code)


def non_public_verification_path(path: str) -> bool:
    return (isinstance(path, str) and path
            and (path.startswith(NON_PUBLIC_VERIFICATION_PREFIXES)
                 or path in NON_PUBLIC_VERIFICATION_FILES))


def digest(value: Any, size: int, label: str) -> None:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(size) + "}", value) is not None,
            label + "_INVALID")


def execution(value: Any) -> tuple[int, int]:
    require(isinstance(value, dict) and set(value) == original.EXECUTION_FIELDS, "EXECUTION_INVALID")
    digest(value["workflow_head_sha"], 40, "WORKFLOW_HEAD")
    try:
        return original.run_key(value)
    except original.ExecutionBindingError as exc:
        raise SnapshotVerificationError(str(exc)) from exc


def code_policy(value: Any) -> dict:
    require(isinstance(value, dict) and set(value) == {"tree_sha", "code_hashes"}, "POLICY_INVALID")
    digest(value["tree_sha"], 40, "VERIFIER_TREE")
    hashes = value["code_hashes"]
    require(isinstance(hashes, dict) and set(hashes) == set(CODE_PATHS), "CODE_PATHS_INVALID")
    for sha in hashes.values():
        digest(sha, 40, "CODE_BLOB")
    return value


def release_identity(value: Any, label: str) -> dict:
    require(isinstance(value, dict) and set(value) == {"head_sha", "release_id", "tree_sha"},
            label + "_IDENTITY_INVALID")
    digest(value["head_sha"], 40, label + "_HEAD")
    digest(value["tree_sha"], 40, label + "_TREE")
    require(isinstance(value["release_id"], str)
            and re.fullmatch(r"v[1-9][0-9]*-[0-9a-f]{12}", value["release_id"]) is not None,
            label + "_RELEASE_ID_INVALID")
    return value


def composition(value: Any) -> dict:
    fields = {"contract", "version", "historical", "runtime", "preserved_blobs", "changed_paths"}
    require(isinstance(value, dict) and set(value) == fields, "COMPOSITION_FIELDS_INVALID")
    require(value["contract"] == "historical-data-current-runtime-composition"
            and value["version"] == "1.0.0", "COMPOSITION_CONTRACT_INVALID")
    historical = release_identity(value["historical"], "HISTORICAL")
    runtime = release_identity(value["runtime"], "RUNTIME")
    require(historical["head_sha"] != runtime["head_sha"]
            and historical["release_id"] != runtime["release_id"], "COMPOSITION_NOT_DISTINCT")
    preserved = value["preserved_blobs"]
    require(isinstance(preserved, dict) and set(preserved) == set(PRESERVED_SURFACES),
            "PRESERVED_SURFACES_INVALID")
    for blob in preserved.values():
        digest(blob, 40, "PRESERVED_BLOB")
    paths = value["changed_paths"]
    require(isinstance(paths, list) and paths == sorted(set(paths)) and bool(paths)
            and all(isinstance(path, str) and path and not path.startswith("/") and ".." not in path.split("/")
                    for path in paths), "CHANGED_PATHS_INVALID")
    return value


def runtime_path(path: str) -> bool:
    if path.startswith((".github/", "app/scripts/", "docs/", "tests/", "scripts/")):
        return True
    if path in {
        "AGENTS.md", "requirements-ci.txt", "app/data/release-bundle.json",
        "app/data/release-provenance.json", "app/service-worker-assets.generated.js",
    }:
        return True
    item = PurePosixPath(path)
    if item.parent == PurePosixPath("app"):
        return item.suffix in {".css", ".html", ".js", ".mjs", ".webmanifest"}
    if item.parent == PurePosixPath("assets"):
        return item.suffix in {".css", ".html", ".js", ".mjs"}
    return False


def validate(value: Any, *, expected_binding: Mapping | None = None) -> dict:
    require(isinstance(value, dict) and set(value) == FIELDS, "FIELDS_INVALID")
    require(value["contract"] == CONTRACT and value["version"] == VERSION, "CONTRACT_INVALID")
    index = original.validate_index(value["original_core_execution"], expected_binding=expected_binding)
    require(index["role"] == "canonical", "ORIGINAL_OWNER_REQUIRED")
    new_key = execution(value["execution"])
    require(new_key[1] == 1, "RERUN_NOT_SUPPORTED")
    require(new_key[0] != original.run_key(index["canonical"])[0], "ORIGINAL_RUN_REUSED")
    code_policy(value["verifier"])
    composed = composition(value["composition"])
    binding = index["binding"]
    require(composed["historical"]["head_sha"] == binding["public_sha"]
            and composed["historical"]["release_id"] == binding["release_id"],
            "HISTORICAL_COMPOSITION_IDENTITY_MISMATCH")
    require(composed["runtime"]["head_sha"] == value["execution"]["workflow_head_sha"]
            and composed["runtime"]["tree_sha"] == value["verifier"]["tree_sha"],
            "RUNTIME_COMPOSITION_IDENTITY_MISMATCH")
    artifact = value["original_artifact"]
    require(isinstance(artifact, dict) and set(artifact) == {"id", "sha256"}
            and type(artifact["id"]) is int and artifact["id"] > 0, "ARTIFACT_INVALID")
    digest(artifact["sha256"], 64, "ARTIFACT_DIGEST")
    return value


def encode(value: dict) -> str:
    return base64.b64encode(original.canonical_bytes(validate(value))).decode("ascii")


def decode(message: str) -> dict:
    require(isinstance(message, str) and 0 < len(message) <= 24000, "NOTICE_INVALID")
    try:
        return validate(original.parse_json(base64.b64decode(message, validate=True)))
    except (ValueError, TypeError) as exc:
        raise SnapshotVerificationError("SNAPSHOT_VERIFICATION_NOTICE_ENCODING_INVALID") from exc


def proof_hash(proof: dict) -> str:
    return original.sha256(original.canonical_bytes(validate(proof)))


def proof_notice(proof: dict) -> dict:
    value = validate(proof)
    run_id, attempt = execution(value["execution"])
    return {
        "artifact_name": f"snapshot-verification-{run_id}-{attempt}",
        "contract": NOTICE_CONTRACT,
        "execution": value["execution"],
        "proof_sha256": proof_hash(value),
        "repository": original.WEB_REPOSITORY,
        "version": NOTICE_VERSION,
    }


def encode_notice(proof: dict) -> str:
    return base64.b64encode(original.canonical_bytes(proof_notice(proof))).decode("ascii")


def decode_notice(message: str) -> dict:
    require(isinstance(message, str) and 0 < len(message) <= 2048, "NOTICE_INVALID")
    try:
        value = original.parse_json(base64.b64decode(message, validate=True))
    except (ValueError, TypeError) as exc:
        raise SnapshotVerificationError("SNAPSHOT_VERIFICATION_NOTICE_ENCODING_INVALID") from exc
    require(isinstance(value, dict) and set(value) == {
        "artifact_name", "contract", "execution", "proof_sha256", "repository", "version",
    }, "NOTICE_FIELDS_INVALID")
    require(value["contract"] == NOTICE_CONTRACT and value["version"] == NOTICE_VERSION,
            "NOTICE_CONTRACT_INVALID")
    run_id, attempt = execution(value["execution"])
    require(value["artifact_name"] == f"snapshot-verification-{run_id}-{attempt}",
            "NOTICE_ARTIFACT_INVALID")
    require(value["repository"] == original.WEB_REPOSITORY, "NOTICE_REPOSITORY_INVALID")
    digest(value["proof_sha256"], 64, "NOTICE_PROOF_DIGEST")
    return value


def validate_attestation(payload: dict) -> dict:
    proof = validate(payload.get("snapshot_verification"))
    index = proof["original_core_execution"]
    require(payload.get("core_execution") == index, "HISTORICAL_INDEX_CHANGED")
    runtime = proof["composition"]["runtime"]
    require(payload.get("head_sha") == runtime["head_sha"]
            and payload.get("release_id") == runtime["release_id"], "SNAPSHOT_RUNTIME_IDENTITY_MISMATCH")
    workflow = payload.get("workflow") or {}
    require(workflow.get("repository") == original.WEB_REPOSITORY
            and str(workflow.get("run_id")) == str(proof["execution"]["run_id"])
            and str(workflow.get("run_attempt")) == str(proof["execution"]["run_attempt"]),
            "VERIFIER_EXECUTION_MISMATCH")
    require(payload.get("publication_state") == "published_and_visually_verified", "VISUAL_EVIDENCE_MISSING")
    return proof


def verify_metadata(*, run: Mapping, job: Mapping, check_run: Mapping, annotations: list,
                    execution_identity: dict, workflow: str, event: str, workflow_id: int,
                    job_name: str, marker: str, marker_message: str, steps: tuple[str, ...]) -> None:
    run_id, attempt = execution(execution_identity)
    head = execution_identity["workflow_head_sha"]
    prefix = "https://api.github.com/repos/" + original.WEB_REPOSITORY
    html = "https://github.com/" + original.WEB_REPOSITORY
    require(run.get("id") == run_id and run.get("run_attempt") == attempt, "RUN_IDENTITY_MISMATCH")
    require((run.get("repository") or {}).get("full_name") == original.WEB_REPOSITORY
            and (run.get("head_repository") or {}).get("full_name") == original.WEB_REPOSITORY,
            "REPOSITORY_MISMATCH")
    require(run.get("head_sha") == head and run.get("head_branch") == "main", "RUN_HEAD_MISMATCH")
    require(type(workflow_id) is int and workflow_id > 0 and run.get("workflow_id") == workflow_id
            and run.get("path") == workflow and run.get("event") == event, "WORKFLOW_MISMATCH")
    require(run.get("url") == f"{prefix}/actions/runs/{run_id}"
            and run.get("html_url") == f"{html}/actions/runs/{run_id}", "RUN_URL_MISMATCH")
    job_id, check_id = job.get("id"), check_run.get("id")
    require(type(job_id) is int and job_id > 0 and type(check_id) is int and check_id > 0, "JOB_ID_INVALID")
    require(job.get("name") == job_name and job.get("run_id") == run_id
            and job.get("run_attempt") == attempt and job.get("head_sha") == head, "JOB_IDENTITY_MISMATCH")
    require(job.get("run_url") == f"{prefix}/actions/runs/{run_id}"
            and job.get("check_run_url") == f"{prefix}/check-runs/{check_id}", "JOB_URL_MISMATCH")
    require(check_run.get("url") == job.get("check_run_url") and check_run.get("name") == job_name
            and check_run.get("head_sha") == head, "CHECK_IDENTITY_MISMATCH")
    require((check_run.get("app") or {}).get("id") == original.GITHUB_ACTIONS_APP_ID
            and (check_run.get("app") or {}).get("slug") == "github-actions", "CHECK_AUTHORITY_MISMATCH")
    require(check_run.get("details_url") == job.get("html_url")
            and job.get("html_url") == f"{html}/actions/runs/{run_id}/job/{job_id}", "CHECK_LINK_MISMATCH")
    matches = [row for row in annotations if row.get("title") == marker]
    require(len(matches) == 1 and matches[0].get("message") == marker_message
            and matches[0].get("path") == workflow and matches[0].get("annotation_level") == "notice",
            "NOTICE_MISMATCH")
    ordered = []
    for step_name in steps:
        found = [s for s in job.get("steps", []) if s.get("name") == step_name]
        require(len(found) == 1 and found[0].get("status") == "completed"
                and found[0].get("conclusion") == "success", "STEP_NOT_VERIFIED")
        number = found[0].get("number")
        require(type(number) is int and number > 0, "STEP_NUMBER_INVALID")
        ordered.append(number)
    require(ordered == sorted(set(ordered)), "STEP_ORDER_INVALID")


def verify_github_proof(proof: dict, *, expected_binding: Mapping, approved_policy: dict,
                        actual_policy: dict, run: Mapping, job: Mapping, check_run: Mapping,
                        annotations: list, workflow_id: int) -> dict:
    value = validate(proof, expected_binding=expected_binding)
    require(code_policy(approved_policy) == code_policy(actual_policy) == value["verifier"],
            "UNAPPROVED_VERIFIER_CODE")
    verify_metadata(run=run, job=job, check_run=check_run, annotations=annotations,
                    execution_identity=value["execution"], workflow=WORKFLOW, event="workflow_dispatch",
                    workflow_id=workflow_id, job_name=VERIFY_JOB, marker=NOTICE_TITLE,
                    marker_message=encode_notice(value), steps=(VERIFY_STEP, EMIT_STEP))
    return value


def watchdog_notice(proof: dict, *, execution_identity: dict,
                    attestation_sha256: str, archive_sha256: str) -> dict:
    value = validate(proof)
    execution(execution_identity)
    digest(attestation_sha256, 64, "ATTESTATION_DIGEST")
    digest(archive_sha256, 64, "ARCHIVE_DIGEST")
    return {"contract": "core-publication-snapshot-watchdog", "version": VERSION,
            "verification_sha256": proof_hash(value),
            "verification": {key: value["execution"][key] for key in original.RUN_FIELDS},
            "execution": execution_identity, "attestation_sha256": attestation_sha256,
            "archive_sha256": archive_sha256,
            "public_sha": value["original_core_execution"]["binding"]["public_sha"],
            "binding_sha256": value["original_core_execution"]["binding_sha256"]}


def encode_watchdog(value: dict) -> str:
    return base64.b64encode(original.canonical_bytes(value)).decode("ascii")


def verify_watchdog(value: dict, *, proof: dict, approved_policy: dict, actual_policy: dict,
                    attestation_sha256: str, archive_sha256: str,
                    run: Mapping, job: Mapping, check_run: Mapping, annotations: list, workflow_id: int) -> dict:
    require(isinstance(value, dict), "WATCHDOG_INVALID")
    require(value == watchdog_notice(proof, execution_identity=value.get("execution"),
                                     attestation_sha256=attestation_sha256, archive_sha256=archive_sha256),
            "WATCHDOG_BINDING_MISMATCH")
    require(code_policy(approved_policy) == code_policy(actual_policy), "UNAPPROVED_WATCHDOG_CODE")
    require(run.get("status") == "completed" and run.get("conclusion") == "success"
            and job.get("status") == "completed" and job.get("conclusion") == "success", "WATCHDOG_NOT_SUCCESSFUL")
    verify_metadata(run=run, job=job, check_run=check_run, annotations=annotations,
                    execution_identity=value["execution"], workflow=WATCHDOG_WORKFLOW, event="workflow_run",
                    workflow_id=workflow_id, job_name=WATCHDOG_JOB, marker=WATCHDOG_NOTICE,
                    marker_message=encode_watchdog(value), steps=(WATCHDOG_STEP,))
    return value
