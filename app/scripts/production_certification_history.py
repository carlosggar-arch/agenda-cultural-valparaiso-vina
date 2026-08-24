from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

SCHEMA_VERSION = "1.0.0"
CONTRACT = "vivamos-production-certification-history"
ENVIRONMENT = "production"
VERIFIED_STATE = "published_and_visually_verified"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class CertificationHistoryError(RuntimeError):
    pass


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise CertificationHistoryError(f"CERTIFICATION_FILE_MISSING path={path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CertificationHistoryError(f"CERTIFICATION_JSON_INVALID path={path}")
    return payload


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


def _record(payload: dict, path: str) -> dict:
    release, head_sha, release_id, fingerprint, state = _identity(payload)
    workflow = payload.get("workflow") or {}
    return {
        "release": release,
        "head_sha": head_sha,
        "release_id": release_id,
        "release_fingerprint": fingerprint,
        "verified_at": str(payload.get("verified_at") or ""),
        "publication_state": state,
        "workflow_run_id": workflow.get("run_id"),
        "path": path,
    }


def _validate_existing(existing: dict, incoming: dict) -> None:
    if _identity(existing) != _identity(incoming):
        raise CertificationHistoryError("CERTIFICATION_IMMUTABLE_PATH_CONFLICT")


def persist_certification(attestation_path: Path, state_root: Path) -> tuple[Path, Path, bool]:
    payload = _read_json(attestation_path)
    release, head_sha, _release_id, _fingerprint, _state = _identity(payload)

    relative = Path("data") / "releases" / f"v{release}" / f"{head_sha}.json"
    archive_path = state_root / relative
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if archive_path.exists():
        _validate_existing(_read_json(archive_path), payload)
    else:
        shutil.copyfile(attestation_path, archive_path)
        created = True

    index_path = state_root / "data" / "index.json"
    if index_path.exists():
        index = _read_json(index_path)
        if index.get("contract") != CONTRACT or index.get("environment") != ENVIRONMENT:
            raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_CONTRACT_INVALID")
        records = list(index.get("certifications") or [])
    else:
        records = []

    record = _record(payload, relative.as_posix())
    key = (record["release"], record["head_sha"])
    matched = [row for row in records if (row.get("release"), row.get("head_sha")) == key]
    if len(matched) > 1:
        raise CertificationHistoryError("CERTIFICATION_HISTORY_DUPLICATE_KEY")
    if matched:
        for field in ("release_id", "release_fingerprint", "publication_state", "path"):
            if matched[0].get(field) != record.get(field):
                raise CertificationHistoryError("CERTIFICATION_HISTORY_INDEX_CONFLICT")
    else:
        records.append(record)

    records.sort(
        key=lambda row: (str(row.get("verified_at") or ""), int(row.get("release") or 0), str(row.get("head_sha") or "")),
        reverse=True,
    )
    latest = records[0] if records else None
    index_payload = {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "environment": ENVIRONMENT,
        "latest": latest,
        "certifications": records,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return archive_path, index_path, created


def main() -> int:
    parser = argparse.ArgumentParser(description="Persist an immutable, per-release production certification history.")
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--state-root", required=True)
    args = parser.parse_args()

    try:
        archive, index, created = persist_certification(Path(args.attestation), Path(args.state_root))
        payload = _read_json(Path(args.attestation))
        print(
            "PRODUCTION_CERTIFICATION_HISTORY_RECORDED "
            f"release=v{payload['release']} head={payload['head_sha']} archive={archive} index={index} "
            f"created={str(created).lower()} immutable=true environment={ENVIRONMENT}"
        )
        return 0
    except (CertificationHistoryError, json.JSONDecodeError, OSError) as exc:
        print(f"PRODUCTION_CERTIFICATION_HISTORY_BLOCKED {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
