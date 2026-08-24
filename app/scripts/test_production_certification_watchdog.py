from __future__ import annotations

import json
import tempfile
from pathlib import Path

from production_certification_history import CertificationHistoryError, persist_certification
from production_certification_watchdog import check_certification


def write_attestation(path: Path, *, release: int, head: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "verified_at": "2026-08-24T10:45:09Z",
                "head_sha": head,
                "release": release,
                "release_id": f"v{release}-fixture",
                "release_fingerprint": f"fingerprint-{release}",
                "workflow": {"run_id": "123"},
                "publication_state": "published_and_visually_verified",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="vivamos-cert-watchdog-") as tmp:
        root = Path(tmp)
        state = root / "state"
        attestation = root / "attestation.json"
        certified_head = "a" * 40
        write_attestation(attestation, release=225, head=certified_head)
        persist_certification(attestation, state)

        match = check_certification(state, certified_head, 225)
        assert match["head_sha"] == certified_head
        assert match["archive_sha256"]

        try:
            check_certification(state, "b" * 40, 225)
        except CertificationHistoryError as exc:
            assert str(exc).startswith("PRODUCTION_UNCERTIFIED")
            assert "expected_release=v225" in str(exc)
        else:
            raise AssertionError("missing deployed head certification must fail closed")

        try:
            check_certification(state, certified_head, 226)
        except CertificationHistoryError as exc:
            assert str(exc).startswith("PRODUCTION_UNCERTIFIED")
        else:
            raise AssertionError("wrong release certification must fail closed")

    print("PRODUCTION_CERTIFICATION_WATCHDOG_TESTS_OK")


if __name__ == "__main__":
    main()
