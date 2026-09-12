from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "core-publication-finalizer-lineage"
VERSION = "1.0.0"
COVERAGE_VERSION = "1.1.0"
PENDING_PATHS = {city: f"app/data/quality/publication-technical-pending-{city}.json" for city in ("valpo", "gijon")}
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


def validate_coverage(coverage: Any) -> dict[str, Any]:
    _require(isinstance(coverage, dict) and set(coverage) == {"contract", "status", "manifests", "pending_units"}, "CORE_LINEAGE_COVERAGE_FIELDS_INVALID")
    _require(coverage["contract"] == "publication-coverage/1", "CORE_LINEAGE_COVERAGE_CONTRACT_INVALID")
    manifests = coverage["manifests"]
    _require(isinstance(manifests, dict) and bool(manifests) and set(manifests) <= set(PENDING_PATHS), "CORE_LINEAGE_COVERAGE_MANIFESTS_INVALID")
    _require(all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in manifests.values()), "CORE_LINEAGE_COVERAGE_HASH_INVALID")
    pending = coverage["pending_units"]
    _require(type(pending) is int and pending >= 0, "CORE_LINEAGE_COVERAGE_COUNT_INVALID")
    _require(coverage["status"] == ("technical_pending" if pending else "complete"), "CORE_LINEAGE_COVERAGE_STATUS_INVALID")
    return json.loads(json.dumps(coverage))


def coverage_from_bundle(repository: Path, bundle: Mapping[str, Any]) -> dict[str, Any] | None:
    """Bind optional coverage to exact packaged bytes, not an editorial claim.

    Core has already checked the closed per-unit decisions. This consumer checks
    their transport identity and exposes pending coverage without downgrading any
    visual, schema, temporal or publication invariant.
    """
    components = bundle.get("components") or {}
    names = {key for key in components if key.startswith("technical_pending_")}
    present = {city for city, relative in PENDING_PATHS.items() if (repository / relative).exists()}
    _require(names == {f"technical_pending_{city}" for city in present}, "CORE_LINEAGE_COVERAGE_COMPONENTS_MISMATCH")
    if not present:
        return None
    manifests, pending = {}, 0
    for city in sorted(present):
        relative = PENDING_PATHS[city]
        path = repository / relative
        _require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(repository.resolve()), "CORE_LINEAGE_COVERAGE_FILE_INVALID")
        raw = path.read_bytes()
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        _require(components[f"technical_pending_{city}"] == {"path": relative, "sha": blob}, "CORE_LINEAGE_COVERAGE_COMPONENT_HASH_MISMATCH")
        manifest = json.loads(raw)
        _require(isinstance(manifest, dict) and manifest.get("contract") == "publication-technical-pending/1"
                 and manifest.get("schema_version") == "1.0.0" and manifest.get("city") == city,
                 "CORE_LINEAGE_COVERAGE_MANIFEST_INVALID")
        units = manifest.get("units")
        _require(isinstance(units, list) and all(isinstance(unit, dict) and unit.get("state") in {"pending", "resolved"}
                 and re.fullmatch(r"unit_[0-9a-f]{24}", str(unit.get("unit_id") or "")) for unit in units), "CORE_LINEAGE_COVERAGE_UNITS_INVALID")
        _require(len({unit["unit_id"] for unit in units}) == len(units), "CORE_LINEAGE_COVERAGE_UNIT_DUPLICATE")
        manifests[city] = sha256_bytes(raw)
        pending += sum(unit["state"] == "pending" for unit in units)
    return validate_coverage({"contract": "publication-coverage/1", "status": "technical_pending" if pending else "complete",
                              "manifests": manifests, "pending_units": pending})


def _committed_coverage(repository: Path, public_sha: str, parent_sha: str,
                        selected_cities: list[str], coverage: dict[str, Any]) -> None:
    for city in coverage["manifests"]:
        relative = PENDING_PATHS[city]
        raw = (repository / relative).read_bytes()
        try:
            committed = subprocess.check_output(["git", "show", f"{public_sha}:{relative}"], cwd=repository, stderr=subprocess.PIPE)
            _require(committed == raw, "CORE_LINEAGE_COVERAGE_NOT_COMMITTED")
        except subprocess.CalledProcessError as exc:
            raise CoreLineageError("CORE_LINEAGE_COVERAGE_COMMIT_EVIDENCE_MISSING") from exc
    # Include absent current files: deleting an unselected city's manifest is
    # also a mutation, not a way to remove its coverage obligation.
    for city, relative in PENDING_PATHS.items():
        if city in selected_cities:
            continue
        try:
            tree = subprocess.check_output(["git", "ls-tree", parent_sha, "--", relative], cwd=repository, text=True, stderr=subprocess.PIPE)
            _require(bool(tree.strip()) == (city in coverage["manifests"]), "CORE_LINEAGE_COVERAGE_UNSELECTED_CHANGED")
            if tree.strip():
                previous = subprocess.check_output(["git", "show", f"{parent_sha}:{relative}"], cwd=repository, stderr=subprocess.PIPE)
                _require(previous == (repository / relative).read_bytes(), "CORE_LINEAGE_COVERAGE_UNSELECTED_CHANGED")
        except subprocess.CalledProcessError as exc:
            raise CoreLineageError("CORE_LINEAGE_COVERAGE_COMMIT_EVIDENCE_MISSING") from exc


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
    with_coverage = payload.get("version") == COVERAGE_VERSION
    _require(set(payload) == expected_fields | ({"coverage"} if with_coverage else set()), "CORE_LINEAGE_FIELDS_INVALID")
    _require(payload.get("contract") == CONTRACT and payload.get("version") in {VERSION, COVERAGE_VERSION}, "CORE_LINEAGE_CONTRACT_INVALID")
    if with_coverage:
        validate_coverage(payload["coverage"])
    _require(("coverage" in receipt) == with_coverage, "CORE_LINEAGE_RECEIPT_COVERAGE_REQUIRED")
    if with_coverage:
        _require(payload["coverage"] == validate_coverage(receipt["coverage"]), "CORE_LINEAGE_RECEIPT_COVERAGE_MISMATCH")
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
    coverage = coverage_from_bundle(repository, bundle)
    _require(coverage == payload.get("coverage"), "CORE_LINEAGE_BUNDLE_COVERAGE_MISMATCH")
    if coverage is not None:
        _committed_coverage(repository, expected_public_sha, parent, payload.get("scope") or [], coverage)
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
