from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA_VERSION = "1.1.0"
CONTRACT = "vivamos-production-certification-history"
ENVIRONMENT = "production"
VERIFIED_STATE = "published_and_visually_verified"
CHAIN_ALGORITHM = "sha256"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HEX256_RE = re.compile(r"^[0-9a-f]{64}$")


class CertificationHistoryError(RuntimeError):
    pass


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise CertificationHistoryError(f"CERTIFICATION_FILE_MISSING path={path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CertificationHistoryError(f"CERTIFICATION_JSON_INVALID path={path}")
    return payload


def _json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _identity(payload: dict) -> tuple[int, str, str, str, str]:
    try:
        release = int(payload.get("release") or 0)
    except (TypeError, ValueError) as exc:
        raise CertificationHistoryError("CERTIFICATION_RELEASE_INVALID") from exc
    head_sha = str(payload.get("head_sha") or "").strip().lower()
    release_id = str(payload.get("release_id") or "").strip()
    fingerprint = str(payload.get("release_fingerprint") or "").strip()
    state = str(payload.get("publication_state") or "").strip()
    if release <= 0:
        raise CertificationHistoryError("CERTIFICATION_RELEASE_INVALID")
    if not SHA_RE.fullmatch(head_sha):
        raise CertificationHistoryError("CERTIFICATION_HEAD_SHA_INVALID")
    if not release_id.startswith(f"v{release}-"):
        raise CertificationHistoryError("CERTIFICATION_RELEASE_ID_INVALID")
    if not fingerprint:
        raise CertificationHistoryError("CERTIFICATION_FINGERPRINT_MISSING")
    if state != VERIFIED_STATE:
        raise CertificationHistoryError("CERTIFICATION_NOT_VISUALLY_VERIFIED")
    return release, head_sha, release_id, fingerprint, state


def _archive_relative(payload: dict) -> Path:
    release, head_sha, *_ = _identity(payload)
    return Path("data") / "releases" / f"v{release}" / f"{head_sha}.json"


def _record(payload: dict, path: str, archive_sha256: str) -> dict:
    release, head_sha, release_id, fingerprint, state = _identity(payload)
    workflow = payload.get("workflow") or {}
    chain = payload.get("history_chain") or {}
    return {
        "release": release,
        "head_sha": head_sha,
        "release_id": release_id,
        "release_fingerprint": fingerprint,
        "verified_at": str(payload.get("verified_at") or ""),
        "publication_state": state,
        "workflow_run_id": workflow.get("run_id"),
        "path": path,
        "archive_sha256": archive_sha256,
        "previous_path": chain.get("previous_path"),
        "previous_archive_sha256": chain.get("previous_archive_sha256"),
        "chain_algorithm": chain.get("algorithm") or (CHAIN_ALGORITHM if chain else None),
    }


def _validate_existing(existing: dict, incoming: dict) -> None:
    if _identity(existing) != _identity(incoming):
        raise CertificationHistoryError("CERTIFICATION_IMMUTABLE_PATH_CONFLICT")


def _load_index(state_root: Path) -> tuple[Path, dict, list[dict]]:
    index_path = state_root / "data" / "index.json"
    if not index_path.exists():
        return index_path, {}, []
    index = _read_json(index_path)
    if index.get("contract") != CONTRACT or index.get("environment") != ENVIRONMENT:
        raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_CONTRACT_INVALID")
    records = list(index.get("certifications") or [])
    if not all(isinstance(row, dict) for row in records):
        raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_ROWS_INVALID")
    return index_path, index, records


def _chronological_key(row: dict) -> tuple[str, int, str]:
    return (
        str(row.get("verified_at") or ""),
        int(row.get("release") or 0),
        str(row.get("head_sha") or ""),
    )


def _hydrate_and_validate_records(state_root: Path, records: list[dict]) -> list[dict]:
    hydrated: list[dict] = []
    keys: set[tuple[int, str]] = set()
    for row in records:
        try:
            release = int(row.get("release") or 0)
        except (TypeError, ValueError) as exc:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_RELEASE_INVALID") from exc
        head_sha = str(row.get("head_sha") or "").strip().lower()
        key = (release, head_sha)
        if key in keys:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_DUPLICATE_KEY")
        keys.add(key)

        relative = Path(str(row.get("path") or ""))
        if not relative.parts or relative.parts[:2] != ("data", "releases") or ".." in relative.parts:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_PATH_INVALID")
        archive = state_root / relative
        payload = _read_json(archive)
        if _identity(payload)[:2] != key:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_ARCHIVE_IDENTITY_MISMATCH")
        actual_sha = _sha256_path(archive)
        declared_sha = str(row.get("archive_sha256") or "")
        if declared_sha and (not HEX256_RE.fullmatch(declared_sha) or declared_sha != actual_sha):
            raise CertificationHistoryError("CERTIFICATION_HISTORY_ARCHIVE_HASH_MISMATCH")

        canonical = _record(payload, relative.as_posix(), actual_sha)
        for field in ("release_id", "release_fingerprint", "publication_state"):
            if row.get(field) is not None and row.get(field) != canonical.get(field):
                raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_CONFLICT")
        hydrated.append(canonical)

    oldest_to_newest = sorted(hydrated, key=_chronological_key)
    previous: dict | None = None
    chain_started = False
    for row in oldest_to_newest:
        archive_payload = _read_json(state_root / row["path"])
        chain = archive_payload.get("history_chain")
        if chain is None:
            if chain_started:
                raise CertificationHistoryError("CERTIFICATION_HISTORY_LEGACY_AFTER_CHAIN")
            previous = row
            continue
        chain_started = True
        if chain.get("algorithm") != CHAIN_ALGORITHM:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_CHAIN_ALGORITHM_INVALID")
        attestation_sha = str(chain.get("attestation_sha256") or "")
        if not HEX256_RE.fullmatch(attestation_sha):
            raise CertificationHistoryError("CERTIFICATION_HISTORY_ATTESTATION_HASH_INVALID")
        expected_path = previous.get("path") if previous else None
        expected_hash = previous.get("archive_sha256") if previous else None
        if chain.get("previous_path") != expected_path:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_PREVIOUS_PATH_MISMATCH")
        if chain.get("previous_archive_sha256") != expected_hash:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_PREVIOUS_HASH_MISMATCH")
        previous = row
    return hydrated


def validate_history(state_root: Path) -> dict:
    index_path, index, records = _load_index(state_root)
    if not index_path.exists():
        raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_MISSING")
    hydrated = _hydrate_and_validate_records(state_root, records)
    hydrated.sort(key=_chronological_key, reverse=True)
    latest = hydrated[0] if hydrated else None
    chain_meta = index.get("chain") or {}
    if latest:
        declared_head_hash = str(chain_meta.get("head_archive_sha256") or "")
        if declared_head_hash and declared_head_hash != latest["archive_sha256"]:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_CHAIN_HEAD_MISMATCH")
        declared_length = chain_meta.get("length")
        if declared_length is not None and int(declared_length) != len(hydrated):
            raise CertificationHistoryError("CERTIFICATION_HISTORY_CHAIN_LENGTH_MISMATCH")
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "environment": ENVIRONMENT,
        "latest": latest,
        "chain": {
            "algorithm": CHAIN_ALGORITHM,
            "length": len(hydrated),
            "head_archive_sha256": latest.get("archive_sha256") if latest else None,
            "anchor_path": hydrated[-1].get("path") if hydrated else None,
        },
        "certifications": hydrated,
    }


def persist_certification(attestation_path: Path, state_root: Path) -> tuple[Path, Path, bool]:
    incoming = _read_json(attestation_path)
    _identity(incoming)
    relative = _archive_relative(incoming)
    archive_path = state_root / relative
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    index_path, _index, records = _load_index(state_root)
    hydrated = _hydrate_and_validate_records(state_root, records) if records else []
    hydrated.sort(key=_chronological_key, reverse=True)
    previous = hydrated[0] if hydrated else None

    created = False
    if archive_path.exists():
        archived_payload = _read_json(archive_path)
        _validate_existing(archived_payload, incoming)
    else:
        archived_payload = dict(incoming)
        archived_payload["history_chain"] = {
            "schema_version": "1.0.0",
            "algorithm": CHAIN_ALGORITHM,
            "attestation_sha256": _sha256_path(attestation_path),
            "previous_path": previous.get("path") if previous else None,
            "previous_archive_sha256": previous.get("archive_sha256") if previous else None,
        }
        archive_path.write_bytes(_json_bytes(archived_payload))
        created = True

    archive_sha = _sha256_path(archive_path)
    record = _record(_read_json(archive_path), relative.as_posix(), archive_sha)
    key = (record["release"], record["head_sha"])
    matched = [row for row in hydrated if (row.get("release"), row.get("head_sha")) == key]
    if len(matched) > 1:
        raise CertificationHistoryError("CERTIFICATION_HISTORY_DUPLICATE_KEY")
    if matched:
        for field in (
            "release_id",
            "release_fingerprint",
            "publication_state",
            "path",
            "archive_sha256",
            "previous_path",
            "previous_archive_sha256",
        ):
            if matched[0].get(field) != record.get(field):
                raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_CONFLICT")
    else:
        hydrated.append(record)

    hydrated.sort(key=_chronological_key, reverse=True)
    latest = hydrated[0] if hydrated else None
    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "environment": ENVIRONMENT,
        "latest": latest,
        "chain": {
            "algorithm": CHAIN_ALGORITHM,
            "length": len(hydrated),
            "head_archive_sha256": latest.get("archive_sha256") if latest else None,
            "anchor_path": hydrated[-1].get("path") if hydrated else None,
        },
        "certifications": hydrated,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(_json_bytes(index_payload))
    validate_history(state_root)
    return archive_path, index_path, created


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist an immutable, chained per-release production certification history.")
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--state-root", required=True)
    args = parser.parse_args()

    try:
        archive, index, created = persist_certification(Path(args.attestation), Path(args.state_root))
        payload = _read_json(Path(args.attestation))
        verified = validate_history(Path(args.state_root))
        print(
            "PRODUCTION_CERTIFICATION_HISTORY_RECORDED "
            f"release=v{payload['release']} head={payload['head_sha']} archive={archive} index={index} "
            f"created={str(created).lower()} immutable=true chain={CHAIN_ALGORITHM} "
            f"chain_length={verified['chain']['length']} environment={ENVIRONMENT}"
        )
        return 0
    except (CertificationHistoryError, json.JSONDecodeError, OSError) as exc:
        print(f"PRODUCTION_CERTIFICATION_HISTORY_BLOCKED {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
