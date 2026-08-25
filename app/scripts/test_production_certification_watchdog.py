from __future__ import annotations

import json
import tempfile
from pathlib import Path

from production_certification_history import CertificationHistoryError, persist_certification
from production_certification_watchdog import check_certification


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "production-certification-watchdog.yml"


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


def assert_workflow_is_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "CERTIFICATION_WATCHDOG_SKIPPED" not in text
    assert "reason=deployment-not-synchronized" in text
    assert "exit 2" in text
    assert "PRODUCTION_DEPLOYMENT_STATE=DEPLOYED" in text
    assert "PRODUCTION_CERTIFICATION_STATE=DATA_CERTIFIED" in text
    assert "attestation-head-mismatch" in text
    assert "dataset-fingerprint-missing" in text
    assert "WEB↔PWA + GitHub Pages↔Cloudflare" in text


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

    assert_workflow_is_fail_closed()
    print("PRODUCTION_CERTIFICATION_WATCHDOG_TESTS_OK")


if __name__ == "__main__":
    main()
