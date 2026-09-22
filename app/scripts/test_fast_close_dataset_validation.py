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

    # A legacy dataset without selection-start evidence cannot claim that a
    # previous local date was the selection day merely because midnight passed.
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

    crossed = payload("2026-09-22T00:04:11+02:00", "2026-09-21")
    crossed["timezone"] = "Europe/Madrid"
    crossed["selection_started_at"] = "2026-09-21T23:58:44+02:00"
    crossed["events"][0]["schedule"] = {"start": "2026-09-22T19:00:00+02:00"}
    validate_payload("gijon", crossed, require_fresh=False)
    recurring = {**crossed, "events": [{"id": "recurring", "schedule": {
        "start": "2026-09-21T13:00:00+02:00",
        "occurrences": [{"start": "2026-09-21T13:00:00+02:00"},
                        {"start": "2026-09-25T13:00:00+02:00"}],
    }}]}
    validate_payload("gijon", recurring, require_fresh=False)
    for field, value, reason in (
        ("selection_started_at", None, "SELECTION_START_INVALID"),
        ("selection_started_at", "not-a-timestamp", "SELECTION_START_INVALID"),
        ("selection_started_at", "2026-09-21T23:58:44-03:00", "SELECTION_TIMEZONE_INVALID"),
        ("selection_started_at", "2026-09-22T00:00:00+02:00", "SELECTION_DATE_MISMATCH"),
        ("generated_at", "2026-09-23T00:04:11+02:00", "SELECTION_WINDOW_INVALID"),
        ("publication_date", "2026-09-20", "SELECTION_DATE_MISMATCH"),
    ):
        invalid = {**crossed, field: value}
        try:
            validate_payload("gijon", invalid, require_fresh=False)
        except ValueError as exc:
            assert reason in str(exc), (field, exc)
        else:
            raise AssertionError(f"accepted inconsistent {field}")
    expired = {**crossed, "events": [{"id": "expired", "schedule": {"start": "2026-09-20"}}]}
    try:
        validate_payload("gijon", expired, require_fresh=False)
    except ValueError as exc:
        assert "FAST_CLOSE_EVENT_EXPIRED" in str(exc)
    else:
        raise AssertionError("expired event accepted")
    expired["events"][0]["schedule"]["start"] = "2026-09-21"
    try:
        validate_payload("gijon", expired, require_fresh=False)
    except ValueError as exc:
        assert "FAST_CLOSE_EVENT_EXPIRED" in str(exc)
    else:
        raise AssertionError("yesterday's occurrence accepted after midnight")
    before_midnight = payload("2026-09-21T23:59:00+02:00", "2026-09-21")
    before_midnight["timezone"] = "Europe/Madrid"
    before_midnight["selection_started_at"] = "2026-09-21T23:58:44+02:00"
    before_midnight["events"][0]["schedule"] = {"start": "2026-09-21T20:00:00+02:00"}
    validate_payload("gijon", before_midnight, require_fresh=False)
    try:
        validate_payload("gijon", before_midnight, require_fresh=True,
                         now_utc=datetime.fromisoformat("2026-09-22T00:05:00+02:00"))
    except ValueError as exc:
        assert "FAST_CLOSE_EVENT_EXPIRED" in str(exc)
    else:
        raise AssertionError("event expired before public write was accepted")

    print("FAST_CLOSE_DATASET_VALIDATION_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
