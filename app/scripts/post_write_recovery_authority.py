"""Strict authority for retransmitting a signed post-write publication.

The original Sigstore bundle remains the authority for the publication bytes.
This contract separately authenticates the protected Core recovery execution,
the explicitly approved Web runtime, and one failed Web delivery that stopped
before emitting a canonical execution index or starting a deployment.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

try:
    from . import publication_execution_binding as binding
except ImportError:
    import publication_execution_binding as binding


PROOF_CONTRACT = "post-write-lineage-transport-recovery"
PROOF_VERSION = "2.0.0"
REFERENCE_CONTRACT = "post-write-recovery-authority-reference"
REFERENCE_VERSION = "1.0.0"
RUNTIME_POLICY_CONTRACT = "post-write-recovery-web-runtime-policy"
RUNTIME_POLICY_VERSION = "1.0.0"
CORE_REPOSITORY = "carlosggar-arch/agenda-cultural-core"
WEB_REPOSITORY = binding.WEB_REPOSITORY
CORE_WORKFLOW = ".github/workflows/finalize-public-agenda.yml"
WEB_WORKFLOW = binding.WORKFLOW
DISPOSITION = "failed_before_canonical_authority_without_deployment"
PROOF_ARTIFACT_PREFIX = "post-write-transport-recovery-"
PRIOR_ARTIFACT_PREFIX = "core-lineage-transport-"

PROOF_FIELDS = {
    "contract", "version", "historical_finalizer_success_claimed", "original",
    "original_artifact", "content_hashes", "recovery", "approved_web_runtime",
    "prior_web_execution",
}
REFERENCE_FIELDS = {
    "contract", "version", "repository", "run_id", "run_attempt", "core_sha",
    "approved_web_sha", "public_sha", "artifact_id", "artifact_name",
    "artifact_digest", "proof_sha256",
}
PRIOR_FIELDS = {
    "repository", "workflow", "run_id", "run_attempt", "workflow_head_sha",
    "disposition", "run_sha256", "jobs_sha256",
}
PRIOR_DISPOSITION_FIELDS = PRIOR_FIELDS | {
    "artifact", "content_hashes", "authority_emitted", "deployment_started",
}
RUNTIME_FIELDS = {"head_sha", "tree_sha", "code_hashes_sha256", "policy_sha256"}


class RecoveryAuthorityError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RecoveryAuthorityError("POST_WRITE_RECOVERY_" + code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(value: Any, size: int, label: str) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(size) + "}", value) is not None,
            label + "_INVALID")
    return value


def positive(value: Any, label: str) -> int:
    require(type(value) is int and value > 0, label + "_INVALID")
    return value


def validate_runtime(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == RUNTIME_FIELDS, "RUNTIME_FIELDS_INVALID")
    for key in ("head_sha", "tree_sha"):
        digest(value[key], 40, "RUNTIME_" + key.upper())
    for key in ("code_hashes_sha256", "policy_sha256"):
        digest(value[key], 64, "RUNTIME_" + key.upper())
    return dict(value)


def validate_prior(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == PRIOR_FIELDS, "PRIOR_FIELDS_INVALID")
    require(value["repository"] == WEB_REPOSITORY and value["workflow"] == WEB_WORKFLOW
            and value["disposition"] == DISPOSITION, "PRIOR_IDENTITY_INVALID")
    positive(value["run_id"], "PRIOR_RUN")
    positive(value["run_attempt"], "PRIOR_ATTEMPT")
    digest(value["workflow_head_sha"], 40, "PRIOR_HEAD")
    digest(value["run_sha256"], 64, "PRIOR_RUN_HASH")
    digest(value["jobs_sha256"], 64, "PRIOR_JOBS_HASH")
    return dict(value)


def validate_prior_disposition(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == PRIOR_DISPOSITION_FIELDS,
            "PRIOR_DISPOSITION_FIELDS_INVALID")
    prior = validate_prior({key: value[key] for key in PRIOR_FIELDS})
    require(value["authority_emitted"] is False and value["deployment_started"] is False,
            "PRIOR_DISPOSITION_INVALID")
    artifact = value["artifact"]
    require(isinstance(artifact, dict) and set(artifact) == {"id", "name", "digest"},
            "PRIOR_ARTIFACT_FIELDS_INVALID")
    positive(artifact["id"], "PRIOR_ARTIFACT_ID")
    require(artifact["name"] == f"{PRIOR_ARTIFACT_PREFIX}{prior['run_id']}-{prior['run_attempt']}-sync",
            "PRIOR_ARTIFACT_NAME_INVALID")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(artifact["digest"])) is not None,
            "PRIOR_ARTIFACT_DIGEST_INVALID")
    hashes = value["content_hashes"]
    require(isinstance(hashes, dict)
            and set(hashes) == {"attestation", "receipt", "sigstore_bundle"},
            "PRIOR_CONTENT_HASH_FIELDS_INVALID")
    for key, item in hashes.items():
        digest(item, 64, "PRIOR_CONTENT_HASH_" + key.upper())
    return dict(value)


def validate_proof(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == PROOF_FIELDS, "PROOF_FIELDS_INVALID")
    require(value["contract"] == PROOF_CONTRACT and value["version"] == PROOF_VERSION
            and value["historical_finalizer_success_claimed"] is False,
            "PROOF_CONTRACT_INVALID")
    original = value["original"]
    require(isinstance(original, dict)
            and original.get("terminal_state") == "PUBLICATION_FAILED"
            and original.get("failure") == "repository_dispatch_property_limit_after_public_write",
            "ORIGINAL_FAILURE_INVALID")
    for key, size in (("core_sha", 40), ("intent_id", 64), ("public_sha", 40)):
        digest(original.get(key), size, "ORIGINAL_" + key.upper())
    for key in ("publisher_run_id", "finalizer_run_id", "finalizer_run_attempt",
                "job_id", "dispatch_step_number"):
        positive(original.get(key), "ORIGINAL_" + key.upper())
    artifact = value["original_artifact"]
    require(isinstance(artifact, dict) and set(artifact) == {"id", "name", "digest"},
            "ORIGINAL_ARTIFACT_FIELDS_INVALID")
    positive(artifact["id"], "ORIGINAL_ARTIFACT_ID")
    require(re.fullmatch(r"publication-lineage-[1-9][0-9]*-[1-9][0-9]*-[1-9][0-9]*",
                         str(artifact["name"])) is not None, "ORIGINAL_ARTIFACT_NAME_INVALID")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(artifact["digest"])) is not None,
            "ORIGINAL_ARTIFACT_DIGEST_INVALID")
    hashes = value["content_hashes"]
    require(isinstance(hashes, dict)
            and set(hashes) == {"attestation", "receipt", "sigstore_bundle", "legacy_dispatch", "job_log"},
            "CONTENT_HASH_FIELDS_INVALID")
    for key, item in hashes.items():
        digest(item, 64, "CONTENT_HASH_" + key.upper())
    recovery = value["recovery"]
    require(isinstance(recovery, dict)
            and set(recovery) == {"repository", "workflow", "run_id", "run_attempt", "core_sha", "approved_web_sha"}
            and recovery["repository"] == CORE_REPOSITORY and recovery["workflow"] == CORE_WORKFLOW,
            "RECOVERY_IDENTITY_INVALID")
    positive(recovery["run_id"], "RECOVERY_RUN")
    positive(recovery["run_attempt"], "RECOVERY_ATTEMPT")
    digest(recovery["core_sha"], 40, "RECOVERY_CORE_SHA")
    digest(recovery["approved_web_sha"], 40, "RECOVERY_WEB_SHA")
    runtime = validate_runtime(value["approved_web_runtime"])
    require(runtime["head_sha"] == recovery["approved_web_sha"], "RUNTIME_HEAD_MISMATCH")
    validate_prior(value["prior_web_execution"])
    return json.loads(json.dumps(value))


def validate_reference(value: Any, *, proof: Mapping[str, Any] | None = None) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == REFERENCE_FIELDS, "REFERENCE_FIELDS_INVALID")
    require(value["contract"] == REFERENCE_CONTRACT and value["version"] == REFERENCE_VERSION
            and value["repository"] == CORE_REPOSITORY, "REFERENCE_CONTRACT_INVALID")
    positive(value["run_id"], "REFERENCE_RUN")
    positive(value["run_attempt"], "REFERENCE_ATTEMPT")
    positive(value["artifact_id"], "REFERENCE_ARTIFACT_ID")
    for key in ("core_sha", "approved_web_sha", "public_sha"):
        digest(value[key], 40, "REFERENCE_" + key.upper())
    digest(value["proof_sha256"], 64, "REFERENCE_PROOF_HASH")
    require(value["artifact_name"] == f"{PROOF_ARTIFACT_PREFIX}{value['run_id']}-{value['run_attempt']}",
            "REFERENCE_ARTIFACT_NAME_INVALID")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", str(value["artifact_digest"])) is not None,
            "REFERENCE_ARTIFACT_DIGEST_INVALID")
    if proof is not None:
        document = validate_proof(dict(proof))
        recovery = document["recovery"]
        require(value["run_id"] == recovery["run_id"]
                and value["run_attempt"] == recovery["run_attempt"]
                and value["core_sha"] == recovery["core_sha"]
                and value["approved_web_sha"] == recovery["approved_web_sha"]
                and value["public_sha"] == document["original"]["public_sha"]
                and value["proof_sha256"] == sha256(canonical_bytes(document)),
                "REFERENCE_PROOF_MISMATCH")
    return dict(value)


def validate_prior_metadata(*, prior: Mapping[str, Any], run: Mapping[str, Any], jobs: Mapping[str, Any]) -> dict[str, Any]:
    expected = validate_prior({key: prior[key] for key in PRIOR_FIELDS})
    require(sha256(canonical_bytes(run)) == expected["run_sha256"], "PRIOR_RUN_BYTES_MISMATCH")
    require(sha256(canonical_bytes(jobs)) == expected["jobs_sha256"], "PRIOR_JOBS_BYTES_MISMATCH")
    require(run.get("id") == expected["run_id"] and run.get("run_attempt") == expected["run_attempt"]
            and run.get("status") == "completed" and run.get("conclusion") == "failure"
            and run.get("path") == WEB_WORKFLOW and run.get("event") == "repository_dispatch"
            and run.get("head_branch") == "main" and run.get("head_sha") == expected["workflow_head_sha"]
            and (run.get("repository") or {}).get("full_name") == WEB_REPOSITORY
            and (run.get("head_repository") or {}).get("full_name") == WEB_REPOSITORY,
            "PRIOR_RUN_IDENTITY_INVALID")
    rows = list(jobs.get("jobs") or [])
    sync = [row for row in rows if row.get("name") == "sync-cloudflare"]
    require(len(sync) == 1 and sync[0].get("run_id") == expected["run_id"]
            and sync[0].get("run_attempt") == expected["run_attempt"]
            and sync[0].get("head_sha") == expected["workflow_head_sha"]
            and sync[0].get("status") == "completed" and sync[0].get("conclusion") == "failure",
            "PRIOR_SYNC_JOB_INVALID")
    steps = {row.get("name"): row for row in sync[0].get("steps") or []}
    require(len(steps) == len(sync[0].get("steps") or []), "PRIOR_STEPS_AMBIGUOUS")
    for name in (binding.VERIFY_STEP, "Preserve Core lineage transport evidence"):
        row = steps.get(name) or {}
        require(row.get("status") == "completed" and row.get("conclusion") == "success",
                "PRIOR_REQUIRED_STEP_INVALID:" + name)
    emit = steps.get(binding.EMIT_STEP) or {}
    require(emit.get("status") == "completed" and emit.get("conclusion") == "failure",
            "PRIOR_EMIT_NOT_FAILED")
    for name in (
        "Create exact-tree handoff preserving deployment history",
        "Require exact deployment-branch parity with candidate",
        "Validate Cloudflare build snapshot and exact release lineage",
        "Push synchronized deployment branch",
        "Fast-close changed dataset freshness and identity",
        "Fast-close deterministic runtime contracts",
        "Wait once for both production origins in parallel",
        "Mark byte deployment, pending visual verification",
    ):
        row = steps.get(name) or {}
        require(row.get("status") == "completed" and row.get("conclusion") == "skipped",
                "PRIOR_DEPLOYMENT_STEP_NOT_SKIPPED:" + name)
    for name in ("production-smoke", "refresh-open-release-prs"):
        matches = [row for row in rows if row.get("name") == name]
        require(len(matches) == 1 and matches[0].get("status") == "completed"
                and matches[0].get("conclusion") == "skipped",
                "PRIOR_DEPLOYMENT_JOB_NOT_SKIPPED:" + name)
    return expected


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def runtime_composition(root: Path, *, historical_sha: str, runtime: Mapping[str, Any]) -> dict[str, Any]:
    """Prove a newer approved verifier did not alter the written release surface."""
    runtime = validate_runtime(dict(runtime))
    digest(historical_sha, 40, "COMPOSITION_HISTORICAL_SHA")
    require(git(root, "rev-parse", "HEAD") == runtime["head_sha"], "RUNTIME_CHECKOUT_MISMATCH")
    require(git(root, "show", "-s", "--format=%T", runtime["head_sha"]) == runtime["tree_sha"],
            "RUNTIME_TREE_MISMATCH")
    require(subprocess.run(["git", "merge-base", "--is-ancestor", historical_sha, runtime["head_sha"]],
                           cwd=root, check=False).returncode == 0, "HISTORICAL_NOT_ANCESTOR")
    changed = [line for line in git(root, "diff", "--name-only", historical_sha, runtime["head_sha"]).splitlines() if line]
    require(bool(changed), "RUNTIME_NOT_DISTINCT")
    allowed_prefixes = (".github/", "app/scripts/", "scripts/", "tests/")
    allowed_files = {"AGENTS.md", "requirements-ci.txt"}
    require(all(path.startswith(allowed_prefixes) or path in allowed_files for path in changed),
            "NON_VERIFIER_SURFACE_CHANGED")
    preserved = (
        "agenda_web.json", "app/data/gijon/agenda_web.json", "fuentes_publicas.json",
        "app/data/source-registry.json", "app/data/quality/source-coverage.json",
        "app/data/quality/event-quality.json", "app/data/quality/release-readiness.json",
        "app/data/venue-registry.json", "app/data/release-bundle.json",
        "app/data/release-provenance.json", "app/service-worker-assets.generated.js",
        "index.html", "manifest.webmanifest", "app/index.html", "app/manifest.webmanifest",
    )
    blobs: dict[str, str] = {}
    for path in preserved:
        old = git(root, "rev-parse", f"{historical_sha}:{path}")
        new = git(root, "rev-parse", f"{runtime['head_sha']}:{path}")
        require(old == new, "PRESERVED_SURFACE_CHANGED:" + path)
        blobs[path] = old
    code_hashes = {path: git(root, "rev-parse", f"{runtime['head_sha']}:{path}") for path in binding.CODE_PATHS}
    require(sha256(canonical_bytes(code_hashes)) == runtime["code_hashes_sha256"],
            "RUNTIME_CODE_HASHES_MISMATCH")
    return {
        "historical_sha": historical_sha,
        "runtime": runtime,
        "changed_paths": sorted(changed),
        "changed_paths_sha256": sha256(canonical_bytes(sorted(changed))),
        "preserved_surfaces_sha256": sha256(canonical_bytes(blobs)),
    }
