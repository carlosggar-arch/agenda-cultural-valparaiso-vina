from __future__ import annotations

import json
import tempfile
from pathlib import Path

from production_certification_history import (
    CONTRACT,
    ENVIRONMENT,
    CertificationHistoryError,
    persist_certification,
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

        original = archive225.read_text(encoding="utf-8")
        write_attestation(first, release=225, head=head225, verified_at="2026-08-24T10:20:00Z")
        _, _, created_again = persist_certification(first, state)
        assert created_again is False
        assert archive225.read_text(encoding="utf-8") == original, "existing certification must remain byte-immutable"

        write_attestation(second, release=226, head=head226, verified_at="2026-08-24T10:30:00Z")
        archive226, _, created226 = persist_certification(second, state)
        assert created226 is True and archive226.is_file()

        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert index["contract"] == CONTRACT
        assert index["environment"] == ENVIRONMENT
        assert index["latest"]["release"] == 226
        assert index["latest"]["head_sha"] == head226
        assert [row["release"] for row in index["certifications"]] == [226, 225]
        assert all(row["path"].startswith("data/releases/v") for row in index["certifications"])

        conflict = root / "conflict.json"
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
