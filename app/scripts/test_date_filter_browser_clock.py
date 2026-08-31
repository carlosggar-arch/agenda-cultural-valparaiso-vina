from __future__ import annotations

from test_date_filter_browser import controlled_reference_instant


def test_uses_generated_at_as_the_historical_reference_instant() -> None:
    assert controlled_reference_instant({
        "generated_at": "2026-08-30T18:00:00-04:00",
        "publication_date": "2026-08-30",
    }) == "2026-08-30T18:00:00-04:00"


def test_falls_back_to_a_stable_local_publication_instant() -> None:
    assert controlled_reference_instant({"publication_date": "2026-08-30"}) == "2026-08-30T12:00:00-04:00"


def test_rejects_a_dataset_without_an_effective_clock() -> None:
    try:
        controlled_reference_instant({})
    except AssertionError as exc:
        assert "controlled reference instant" in str(exc)
    else:
        raise AssertionError("missing effective clock was accepted")
