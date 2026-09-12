"""Pure execution binding shared by Core and Web.

This is an index, NEVER a signature verifier. Callers must authenticate the
original Core Sigstore bundle/receipt first. GitHub metadata and the authorised
workflow's successful verification/emission steps bind the index to its run.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Mapping

CONTRACT = "core-publication-execution-binding"
VERSION = "1.0.0"
NOTICE_TITLE = "CORE_PUBLICATION_EXECUTION_V1"
VERIFY_STEP = "Verify detached Core publication lineage"
EMIT_STEP = "Bind authenticated Core execution before deployment"
WORKFLOW = ".github/workflows/publish.yml"
WEB_REPOSITORY = "carlosggar-arch/agenda-cultural-valparaiso-vina"
GITHUB_ACTIONS_APP_ID = 15368
CODE_PATHS = (
    ".github/workflows/publish.yml",
    ".github/workflows/production-certification-watchdog.yml",
    "app/scripts/publication_execution_binding.py",
    "app/scripts/publication_execution_github.py",
    "app/scripts/publication_execution_routing.py",
    "app/scripts/verify_core_publication_bundle.py",
    "app/scripts/core_publication_lineage.py",
    "app/scripts/release_finalizer.py",
    "app/scripts/production_release_chain.py",
    "app/scripts/production_release_attestation.py",
    "app/scripts/production_certification_history.py",
)
BINDING_FIELDS = {
    "core_sha", "intent_id", "publisher", "finalizer", "public_sha", "parent_sha",
    "release_id", "acquisition_shas", "fence_sha256", "lineage_sha256",
    "receipt_sha256", "release_bundle_sha256", "sigstore_bundle_sha256",
}
INDEX_FIELDS = {"contract", "version", "binding", "binding_sha256", "execution", "canonical", "role"}
RUN_FIELDS = {"run_id", "run_attempt"}
EXECUTION_FIELDS = RUN_FIELDS | {"workflow_head_sha"}


class ExecutionBindingError(RuntimeError):
    pass


def require(value: bool, code: str) -> None:
    if not value:
        raise ExecutionBindingError("CORE_EXECUTION_" + code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def parse_json(raw: bytes | str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_object)
    except (ValueError, UnicodeError) as exc:
        raise ExecutionBindingError("CORE_EXECUTION_JSON_INVALID") from exc


def _digest(value: Any, length: int, label: str) -> None:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is not None,
            label + "_INVALID")


def run_key(value: Mapping[str, Any]) -> tuple[int, int]:
    require(isinstance(value, Mapping), "RUN_INVALID")
    for field in RUN_FIELDS:
        require(type(value.get(field)) is int and value[field] > 0, "RUN_INVALID")
    return value["run_id"], value["run_attempt"]


def validate_binding(binding: Any) -> dict[str, Any]:
    require(isinstance(binding, dict) and set(binding) == BINDING_FIELDS, "BINDING_FIELDS_INVALID")
    for field in ("core_sha", "public_sha", "parent_sha"):
        _digest(binding[field], 40, field.upper())
    for field in ("intent_id", "fence_sha256", "lineage_sha256", "receipt_sha256",
                  "release_bundle_sha256", "sigstore_bundle_sha256"):
        _digest(binding[field], 64, field.upper())
    for field in ("publisher", "finalizer"):
        require(isinstance(binding[field], dict) and set(binding[field]) == RUN_FIELDS, "RUN_FIELDS_INVALID")
        run_key(binding[field])
    require(isinstance(binding["release_id"], str) and
            re.fullmatch(r"v[1-9][0-9]*-[0-9a-f]{12}", binding["release_id"]) is not None, "RELEASE_INVALID")
    acquisitions = binding["acquisition_shas"]
    require(isinstance(acquisitions, dict) and bool(acquisitions), "ACQUISITIONS_INVALID")
    require(all(city in {"valpo", "gijon"} for city in acquisitions), "ACQUISITIONS_INVALID")
    for value in acquisitions.values():
        _digest(value, 40, "ACQUISITION_SHA")
    return dict(binding)


def binding_from_verified_bytes(*, lineage: bytes, receipt: bytes,
                                release_bundle: bytes, sigstore_bundle: bytes) -> dict[str, Any]:
    """Build exact-byte identity AFTER the unchanged cryptographic verifier."""
    claim = parse_json(lineage)
    require(isinstance(claim, dict) and claim.get("contract") == "core-publication-finalizer-lineage",
            "LINEAGE_INVALID")
    require(claim.get("receipt_sha256") == sha256(receipt), "RECEIPT_HASH_MISMATCH")
    require(claim.get("release_bundle_sha256") == sha256(release_bundle), "RELEASE_BUNDLE_HASH_MISMATCH")
    bundle = parse_json(release_bundle)
    require(isinstance(bundle, dict) and claim.get("release_id") == bundle.get("release_id"),
            "RELEASE_ID_MISMATCH")
    public = claim.get("public") or {}
    return validate_binding({
        "core_sha": claim.get("core_sha"), "intent_id": claim.get("intent_id"),
        "publisher": claim.get("publisher"), "finalizer": claim.get("finalizer"),
        "public_sha": public.get("sha"), "parent_sha": public.get("parent_sha"),
        "release_id": claim.get("release_id"), "acquisition_shas": claim.get("acquisition_shas"),
        "fence_sha256": sha256(canonical_bytes(claim.get("pre_write_acquisition_fence"))),
        "lineage_sha256": sha256(lineage), "receipt_sha256": sha256(receipt),
        "release_bundle_sha256": sha256(release_bundle),
        "sigstore_bundle_sha256": sha256(sigstore_bundle),
    })


def build_index(*, binding: dict[str, Any], run_id: int, run_attempt: int,
                workflow_head_sha: str, canonical: Mapping[str, Any] | None = None) -> dict[str, Any]:
    execution = {"run_id": run_id, "run_attempt": run_attempt, "workflow_head_sha": workflow_head_sha}
    owner = dict(canonical) if canonical is not None else {"run_id": run_id, "run_attempt": run_attempt}
    return validate_index({
        "contract": CONTRACT, "version": VERSION, "binding": binding,
        "binding_sha256": sha256(canonical_bytes(validate_binding(binding))),
        "execution": execution, "canonical": owner,
        "role": "canonical" if run_key(owner) == run_key(execution) else "delegated",
    })


def validate_index(value: Any, *, expected_binding: Mapping[str, Any] | None = None) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == INDEX_FIELDS, "INDEX_FIELDS_INVALID")
    require(value["contract"] == CONTRACT and value["version"] == VERSION, "CONTRACT_INVALID")
    binding = validate_binding(value["binding"])
    require(value["binding_sha256"] == sha256(canonical_bytes(binding)), "BINDING_HASH_MISMATCH")
    if expected_binding is not None:
        require(binding == dict(expected_binding), "BINDING_MISMATCH")
    execution, owner = value["execution"], value["canonical"]
    require(isinstance(execution, dict) and set(execution) == EXECUTION_FIELDS, "EXECUTION_FIELDS_INVALID")
    require(isinstance(owner, dict) and set(owner) == RUN_FIELDS, "OWNER_FIELDS_INVALID")
    _digest(execution["workflow_head_sha"], 40, "WORKFLOW_HEAD")
    same = run_key(execution) == run_key(owner)
    require(value["role"] == ("canonical" if same else "delegated"), "ROLE_INVALID")
    return dict(value)


def encode_notice(index: Mapping[str, Any]) -> str:
    return base64.b64encode(canonical_bytes(validate_index(dict(index)))).decode("ascii")


def parse_notice(message: str) -> dict[str, Any]:
    require(isinstance(message, str) and len(message) <= 16000, "NOTICE_INVALID")
    try:
        raw = base64.b64decode(message.strip(), validate=True)
    except (ValueError, TypeError) as exc:
        raise ExecutionBindingError("CORE_EXECUTION_NOTICE_ENCODING_INVALID") from exc
    return validate_index(parse_json(raw))


def verify_github_index(index: dict[str, Any], *, run: Mapping[str, Any],
                        job: Mapping[str, Any], check_run: Mapping[str, Any],
                        annotations: list[dict[str, Any]], expected_binding: Mapping[str, Any],
                        workflow_id: int, expected_code_hashes: Mapping[str, str],
                        actual_code_hashes: Mapping[str, str]) -> dict[str, Any]:
    """Authenticate an index's execution provenance, NOT its Core signature.

    The index is only a digest/reference transported by GitHub Checks. Authority
    requires the independently verified original Core signature, the exact
    authorised workflow source and GitHub's own run/job/step metadata together.
    A failed later deployment does not erase its authenticated canonical claim.
    """
    value = validate_index(index, expected_binding=expected_binding)
    run_id, attempt = run_key(value["execution"])
    head = value["execution"]["workflow_head_sha"]
    prefix = "https://api.github.com/repos/" + WEB_REPOSITORY
    html_prefix = "https://github.com/" + WEB_REPOSITORY
    require(run.get("id") == run_id and run.get("run_attempt") == attempt, "RUN_IDENTITY_MISMATCH")
    require((run.get("repository") or {}).get("full_name") == WEB_REPOSITORY
            and (run.get("head_repository") or {}).get("full_name") == WEB_REPOSITORY,
            "RUN_REPOSITORY_MISMATCH")
    require(run.get("head_sha") == head and run.get("head_branch") == "main", "RUN_HEAD_MISMATCH")
    require(type(workflow_id) is int and workflow_id > 0 and run.get("workflow_id") == workflow_id
            and run.get("path") == WORKFLOW and run.get("event") == "repository_dispatch",
            "RUN_WORKFLOW_MISMATCH")
    require(run.get("url") == f"{prefix}/actions/runs/{run_id}"
            and run.get("html_url") == f"{html_prefix}/actions/runs/{run_id}", "RUN_URL_MISMATCH")
    require(set(expected_code_hashes) == set(CODE_PATHS)
            and set(actual_code_hashes) == set(CODE_PATHS), "CODE_PATHS_INVALID")
    for path in CODE_PATHS:
        _digest(expected_code_hashes[path], 40, "CODE_BLOB")
        _digest(actual_code_hashes[path], 40, "CODE_BLOB")
    require(dict(actual_code_hashes) == dict(expected_code_hashes), "UNAUTHORISED_WORKFLOW_CODE")
    job_id, check_id = job.get("id"), check_run.get("id")
    require(type(job_id) is int and job_id > 0 and type(check_id) is int and check_id > 0,
            "JOB_CHECK_ID_INVALID")
    require(job.get("name") == "sync-cloudflare" and job.get("run_id") == run_id
            and job.get("run_attempt") == attempt and job.get("head_sha") == head,
            "JOB_IDENTITY_MISMATCH")
    require(job.get("run_url") == f"{prefix}/actions/runs/{run_id}"
            and job.get("check_run_url") == f"{prefix}/check-runs/{check_id}", "JOB_URL_MISMATCH")
    require(check_run.get("url") == f"{prefix}/check-runs/{check_id}"
            and check_run.get("head_sha") == head and check_run.get("name") == "sync-cloudflare",
            "CHECK_IDENTITY_MISMATCH")
    app = check_run.get("app") or {}
    require(app.get("id") == GITHUB_ACTIONS_APP_ID and app.get("slug") == "github-actions",
            "CHECK_AUTHORITY_MISMATCH")
    require(check_run.get("details_url") == job.get("html_url")
            and job.get("html_url") == f"{html_prefix}/actions/runs/{run_id}/job/{job_id}",
            "CHECK_JOB_LINK_MISMATCH")
    markers = [row for row in annotations if row.get("title") == NOTICE_TITLE]
    require(len(markers) == 1, "NOTICE_COUNT_INVALID")
    marker = markers[0]
    require(marker.get("path") == WORKFLOW and marker.get("annotation_level") == "notice",
            "NOTICE_ORIGIN_INVALID")
    require(parse_notice(marker.get("message")) == value, "NOTICE_CONTENT_MISMATCH")
    steps = job.get("steps")
    require(isinstance(steps, list), "STEPS_MISSING")
    numbers = []
    for name in (VERIFY_STEP, EMIT_STEP):
        matches = [step for step in steps if step.get("name") == name]
        require(len(matches) == 1, "STEP_AMBIGUOUS")
        step = matches[0]
        require(step.get("status") == "completed" and step.get("conclusion") == "success",
                "STEP_NOT_VERIFIED")
        require(type(step.get("number")) is int and step["number"] > 0, "STEP_ORDER_INVALID")
        numbers.append(step["number"])
    require(numbers[0] < numbers[1], "STEP_ORDER_INVALID")
    return value


def select_root(indices: list[dict[str, Any]], *, expected_binding: Mapping[str, Any]) -> dict[str, Any] | None:
    """Choose an explicit unique authority graph, never chronology or greenness.

    All supplied indices MUST already have passed GitHub metadata/code/step
    verification. Conflicting evidence for the expected public commit fails
    even when another execution succeeded. Exact duplicate API deliveries are
    harmless, but two canonical roots or a missing/crossed alias are not.
    """
    relevant: dict[tuple[int, int], dict[str, Any]] = {}
    for candidate in indices:
        value = validate_index(candidate)
        if value["binding"]["public_sha"] != expected_binding["public_sha"]:
            continue
        validate_index(value, expected_binding=expected_binding)
        key = run_key(value["execution"])
        require(key not in relevant or relevant[key] == value, "CONTRADICTORY_EXECUTION")
        relevant[key] = value
    if not relevant:
        return None
    roots = [value for value in relevant.values() if value["role"] == "canonical"]
    require(len(roots) <= 1, "CONTRADICTORY_ROOTS")
    if not roots:
        raise ExecutionBindingError("CORE_EXECUTION_ROOT_MISSING")
    root = roots[0]
    owner = run_key(root["execution"])
    for value in relevant.values():
        require(run_key(value["canonical"]) == owner, "CROSSED_OWNER")
    return root
