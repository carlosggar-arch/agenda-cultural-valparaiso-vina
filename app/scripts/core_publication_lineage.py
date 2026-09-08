from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "core-publication-finalizer-lineage"
VERSION = "1.0.0"
CORE_REPOSITORY = "carlosggar-arch/agenda-cultural-core"
PUBLIC_REPOSITORY = "carlosggar-arch/agenda-cultural-valparaiso-vina"
CANONICAL_WRITER = ".github/workflows/finalize-public-agenda.yml"


class CoreLineageError(RuntimeError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise CoreLineageError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_hash(payload: Mapping[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "attestation_sha256"}
    raw = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(raw)


def validate(*, attestation_bytes: bytes, receipt_bytes: bytes, repository: Path, expected_public_sha: str) -> dict[str, Any]:
    try:
        payload = json.loads(attestation_bytes)
        receipt = json.loads(receipt_bytes)
    except json.JSONDecodeError as exc:
        raise CoreLineageError("CORE_LINEAGE_JSON_INVALID") from exc
    _require(isinstance(payload, dict) and isinstance(receipt, dict), "CORE_LINEAGE_SHAPE_INVALID")
    expected_fields = {
        "contract", "version", "core_repository", "public_repository", "core_sha", "intent_id",
        "publisher", "finalizer", "public", "scope", "acquisition_shas", "release_id",
        "receipt_sha256", "release_bundle_sha256", "preservation", "pre_write_acquisition_fence",
        "canonical_writer", "generated_at", "attestation_sha256",
    }
    _require(set(payload) == expected_fields, "CORE_LINEAGE_FIELDS_INVALID")
    _require(payload.get("contract") == CONTRACT and payload.get("version") == VERSION, "CORE_LINEAGE_CONTRACT_INVALID")
    _require(payload.get("core_repository") == CORE_REPOSITORY and payload.get("public_repository") == PUBLIC_REPOSITORY, "CORE_LINEAGE_REPOSITORY_INVALID")
    _require(payload.get("canonical_writer") == CANONICAL_WRITER, "CORE_LINEAGE_WRITER_INVALID")
    _require(payload.get("attestation_sha256") == canonical_hash(payload), "CORE_LINEAGE_HASH_INVALID")
    _require(payload.get("receipt_sha256") == sha256_bytes(receipt_bytes), "CORE_LINEAGE_RECEIPT_HASH_INVALID")
    public = payload.get("public") or {}
    _require(public.get("sha") == expected_public_sha, "CORE_LINEAGE_PUBLIC_SHA_MISMATCH")
    parent = subprocess.check_output(["git", "rev-parse", f"{expected_public_sha}^"], cwd=repository, text=True).strip()
    _require(public.get("parent_sha") == parent, "CORE_LINEAGE_PARENT_SHA_MISMATCH")
    _require(subprocess.check_output(["git", "rev-list", "--count", f"{parent}..{expected_public_sha}"], cwd=repository, text=True).strip() == "1", "CORE_LINEAGE_NOT_DIRECT_CHILD")
    bundle_path = repository / "app/data/release-bundle.json"
    _require(payload.get("release_bundle_sha256") == sha256_bytes(bundle_path.read_bytes()), "CORE_LINEAGE_BUNDLE_HASH_INVALID")
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    _require(payload.get("release_id") == bundle.get("release_id"), "CORE_LINEAGE_RELEASE_ID_MISMATCH")
    publisher, finalizer = receipt.get("publisher") or {}, receipt.get("finalizer") or {}
    receipt_public, fence = receipt.get("public") or {}, receipt.get("pre_write_acquisition_fence") or {}
    _require(receipt.get("contract") == "canonical-publication-receipt", "CORE_LINEAGE_RECEIPT_CONTRACT_INVALID")
    _require(payload.get("publisher") == {"run_id": publisher.get("run_id"), "run_attempt": publisher.get("run_attempt")}, "CORE_LINEAGE_PUBLISHER_MISMATCH")
    _require(payload.get("finalizer") == {"run_id": finalizer.get("run_id"), "run_attempt": finalizer.get("run_attempt")}, "CORE_LINEAGE_FINALIZER_MISMATCH")
    _require(payload.get("core_sha") == publisher.get("source_ref") and payload.get("intent_id") == fence.get("intent_id"), "CORE_LINEAGE_IDENTITY_MISMATCH")
    _require(payload.get("public") == {"parent_sha": receipt_public.get("before_sha"), "sha": receipt_public.get("after_sha")}, "CORE_LINEAGE_RECEIPT_PUBLIC_MISMATCH")
    _require(payload.get("scope") == sorted(receipt.get("scope", {}).get("selected_cities") or []), "CORE_LINEAGE_SCOPE_MISMATCH")
    _require(payload.get("acquisition_shas") == fence.get("acquisition_shas"), "CORE_LINEAGE_ACQUISITION_MISMATCH")
    _require(payload.get("pre_write_acquisition_fence") == fence, "CORE_LINEAGE_FENCE_MISMATCH")
    _require(payload.get("preservation") == {"gijon": "pass", "valparaiso": "pass"}, "CORE_LINEAGE_PRESERVATION_INVALID")
    _require(re.fullmatch(r"[0-9a-f]{64}", str(payload.get("intent_id") or "")) is not None, "CORE_LINEAGE_INTENT_INVALID")
    return payload
