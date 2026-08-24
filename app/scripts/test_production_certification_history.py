from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from production_certification_history import (
    CHAIN_ALGORITHM,
    CONTRACT,
    ENVIRONMENT,
    CertificationHistoryError,
    persist_certification,
    validate_history,
)


def write_attestation(path: Path, *, release: int, head: str, verified_at: str, release_id: str | None = None) -> None:
    payload = {
        "schema_version": "1.0.0",
        "verified_at": verified_at,
        "head_sha": head,
        "release": release,
        "release_id": release_id or f"v{release}-fixture",
        "release_fingerprint": f"fingerprint-{release}",
        "workflow": {"run_id": str(release * 1000)},
        "publication_state": "published_and_visually_verified",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="vivamos-cert-history-") as tmp:
        root = Path(tmp)
        state = root / "state"
        first = root / "first.json"
        second = root / "second.json"
        head225 = "a" * 40
        head226 = "b" * 40

        write_attestation(first, release=225, head=head225, verified_at="2026-08-24T10:10:00Z")
        archive225, index_path, created = persist_certification(first, state)
        assert created is True
        assert archive225 == state / "data/releases/v225" / f"{head225}.json"
        assert archive225.is_file()
        payload225 = json.loads(archive225.read_text(encoding="utf-8"))
        assert payload225["history_chain"]["algorithm"] == CHAIN_ALGORITHM
        assert payload225["history_chain"]["previous_path"] is None
        assert payload225["history_chain"]["previous_archive_sha256"] is None
        assert len(payload225["history_chain"]["attestation_sha256"]) == 64

        original = archive225.read_text(encoding="utf-8")
        write_attestation(first, release=225, head=head225, verified_at="2026-08-24T10:20:00Z")
        _, _, created_again = persist_certification(first, state)
        assert created_again is False
        assert archive225.read_text(encoding="utf-8") == original, "existing certification must remain byte-immutable"

        write_attestation(second, release=226, head=head226, verified_at="2026-08-24T10:30:00Z")
        archive226, _, created226 = persist_certification(second, state)
        assert created226 is True and archive226.is_file()
        payload226 = json.loads(archive226.read_text(encoding="utf-8"))
        assert payload226["history_chain"]["previous_path"] == f"data/releases/v225/{head225}.json"
        assert payload226["history_chain"]["previous_archive_sha256"] == sha256(archive225)

        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert index["contract"] == CONTRACT
        assert index["environment"] == ENVIRONMENT
        assert index["latest"]["release"] == 226
        assert index["latest"]["head_sha"] == head226
        assert [row["release"] for row in index["certifications"]] == [226, 225]
        assert all(row["path"].startswith("data/releases/v") for row in index["certifications"])
        assert index["chain"]["algorithm"] == CHAIN_ALGORITHM
        assert index["chain"]["length"] == 2
        assert index["chain"]["head_archive_sha256"] == sha256(archive226)
        assert validate_history(state)["latest"]["head_sha"] == head226

        # Mutating a historical archive must invalidate both the archive hash and chain.
        tampered = json.loads(archive225.read_text(encoding="utf-8"))
        tampered["release_fingerprint"] = "tampered"
        archive225.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            validate_history(state)
        except CertificationHistoryError as exc:
            assert "ARCHIVE_HASH_MISMATCH" in str(exc) or "PREVIOUS_HASH_MISMATCH" in str(exc)
        else:
            raise AssertionError("historical archive tampering must fail closed")

    with tempfile.TemporaryDirectory(prefix="vivamos-cert-conflict-") as tmp:
        root = Path(tmp)
        state = root / "state"
        first = root / "first.json"
        conflict = root / "conflict.json"
        head225 = "c" * 40
        write_attestation(first, release=225, head=head225, verified_at="2026-08-24T10:10:00Z")
        persist_certification(first, state)
        write_attestation(conflict, release=225, head=head225, verified_at="2026-08-24T10:40:00Z", release_id="v225-different")
        try:
            persist_certification(conflict, state)
        except CertificationHistoryError as exc:
            assert "IMMUTABLE_PATH_CONFLICT" in str(exc)
        else:
            raise AssertionError("same release/head with different identity must fail closed")

    print("PRODUCTION_CERTIFICATION_HISTORY_TESTS_OK")


if __name__ == "__main__":
    main()
