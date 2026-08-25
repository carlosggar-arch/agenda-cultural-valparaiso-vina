from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "app/scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "app/scripts"))

from fast_close_dataset_validation import requires_freshness, validate_payload


def payload(generated_at: str, publication_date: str) -> dict:
    return {
        "generated_at": generated_at,
        "publication_date": publication_date,
        "timezone": "America/Santiago",
        "counts": {"total": 1},
        "events": [{"id": "event-1"}],
    }


def main() -> int:
    old = "2026-08-21T04:02:51-04:00"
    assert requires_freshness(changed=True, current_generated_at=old, previous_generated_at=old) is False
    assert requires_freshness(changed=True, current_generated_at=old, previous_generated_at=None) is True
    assert requires_freshness(
        changed=True,
        current_generated_at="2026-08-25T08:00:00-04:00",
        previous_generated_at=old,
    ) is True
    assert requires_freshness(changed=False, current_generated_at=old, previous_generated_at=old) is False

    # A semantic-only rewrite can be old without pretending to be a fresh
    # ingestion, provided its generation metadata is internally coherent.
    validate_payload(
        "valparaiso",
        payload(old, "2026-08-21"),
        require_fresh=False,
        now_utc=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
    )

    # A genuinely regenerated dataset remains subject to the strict six-hour
    # freshness window.
    try:
        validate_payload(
            "valparaiso",
            payload(old, "2026-08-21"),
            require_fresh=True,
            now_utc=datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        assert "FAST_CLOSE_DATASET_STALE" in str(exc)
    else:
        raise AssertionError("stale regenerated dataset was accepted")

    # publication_date is always required to describe the generated_at local
    # calendar date, regardless of whether freshness itself is required.
    try:
        validate_payload(
            "valparaiso",
            payload(old, "2026-08-20"),
            require_fresh=False,
        )
    except ValueError as exc:
        assert "FAST_CLOSE_PUBLICATION_DATE_MISMATCH" in str(exc)
    else:
        raise AssertionError("inconsistent publication metadata was accepted")

    print("FAST_CLOSE_DATASET_VALIDATION_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
