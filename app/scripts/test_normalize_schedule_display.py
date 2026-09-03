from __future__ import annotations

from pathlib import Path

import normalize_schedule_display as normalizer


def test_gallery_flattened_hours_become_ranges() -> None:
    schedule = {
        "mode": "multi_day",
        "start": "2026-08-18T10:00:00-04:00",
        "end": "2026-08-21",
        "display_text": "2026-08-18 · 10:00, 18:00, 11:00, 17:00",
    }
    fields = normalizer.normalize_schedule(schedule)
    assert fields == ["display_text"]
    assert schedule["display_text"] == "2026-08-18 – 2026-08-21 · 10:00–18:00 · 11:00–17:00"


def test_artequin_flattened_hours_become_ranges() -> None:
    schedule = {
        "mode": "multi_day",
        "start": "2026-08-19T18:30:00-04:00",
        "end": "2026-08-22",
        "display_text": "2026-08-19 · 18:30, 20:00, 10:00, 14:00",
    }
    normalizer.normalize_schedule(schedule)
    assert schedule["display_text"] == "2026-08-19 – 2026-08-22 · 18:30–20:00 · 10:00–14:00"


def test_simple_two_clock_comma_becomes_interval() -> None:
    schedule = {
        "mode": "multi_day",
        "start": "2026-08-18T15:00:00-04:00",
        "end": "2026-08-28",
        "display_text": "2026-08-18 · 15:00, 16:00",
        "occurrences": [],
    }
    fields = normalizer.normalize_schedule(schedule)
    assert fields == ["display_text"]
    assert schedule["display_text"] == "2026-08-18 – 2026-08-28 · 15:00–16:00"


def test_same_day_two_clock_comma_becomes_interval() -> None:
    schedule = {
        "mode": "single",
        "start": "2026-08-22T11:30:00-04:00",
        "end": "2026-08-22",
        "display_text": "2026-08-22 · 11:30, 13:00",
        "occurrences": [],
    }
    normalizer.normalize_schedule(schedule)
    assert schedule["display_text"] == "2026-08-22 · 11:30–13:00"


def test_start_only_is_not_given_an_invented_end() -> None:
    schedule = {
        "mode": "single",
        "start": "2026-08-22T11:30:00-04:00",
        "end": None,
        "display_text": "2026-08-22 · 11:30",
        "occurrences": [],
    }
    assert normalizer.normalize_schedule(schedule) == []
    assert schedule["display_text"] == "2026-08-22 · 11:30"


def test_structured_multiple_sessions_are_preserved_in_gijon() -> None:
    schedule = {
        "mode": "single",
        "start": "2026-08-22T11:30:00+02:00",
        "end": "2026-08-22",
        "display_text": "22 ago · 11:30, 13:00",
        "occurrences": [
            {"start": "2026-08-22T11:30:00+02:00", "end": None},
            {"start": "2026-08-22T13:00:00+02:00", "end": None},
        ],
    }
    assert normalizer.normalize_schedule(schedule) == []
    assert schedule["display_text"] == "22 ago · 11:30, 13:00"


def test_rich_gijon_multiday_sessions_are_preserved() -> None:
    schedule = {
        "mode": "recurring",
        "start": "2026-08-25T15:30:00+02:00",
        "end": "2026-08-30",
        "display_text": "25 ago · 15:30 y 18:15; 26 ago · 14:30 y 17:45; 27 ago · 12:00, 14:15 y 18:00",
        "occurrences": [
            {"start": "2026-08-25T15:30:00+02:00", "end": None},
            {"start": "2026-08-25T18:15:00+02:00", "end": None},
            {"start": "2026-08-26T14:30:00+02:00", "end": None},
        ],
    }
    assert normalizer.normalize_schedule(schedule) == []


def test_all_day_sentinel_becomes_date_only() -> None:
    schedule = {
        "mode": "multi_day",
        "start": "2026-08-06T00:00:00-04:00",
        "end": "2026-10-04T23:59:00-03:00",
        "display_text": "mié, 6 ago – 4 oct · 00:00–23:59",
    }
    fields = normalizer.normalize_schedule(schedule)
    assert set(fields) == {"display_text", "start", "end"}
    assert schedule["start"] == "2026-08-06"
    assert schedule["end"] == "2026-10-04"
    assert schedule["display_text"] == "2026-08-06 – 2026-10-04"


def test_opening_hours_separate_from_event_range() -> None:
    schedule = {
        "mode": "multi_day",
        "start": "2026-08-14T10:00:00-04:00",
        "end": "2026-10-04T18:00:00-03:00",
        "display_text": "14-08-2026 · 10:00 – 04-10-2026 · 18:00",
        "opening_hours": {"display_text": "Martes a domingo · 10:00–18:00"},
    }
    normalizer.normalize_schedule(schedule)
    assert schedule["display_text"] == "2026-08-14 – 2026-10-04"
    assert schedule["opening_hours"]["display_text"] == "Martes a domingo · 10:00–18:00"


def test_real_multiple_session_times_are_not_paired_without_timed_start() -> None:
    schedule = {
        "mode": "multi_day",
        "start": "2026-08-17",
        "end": "2026-08-23",
        "display_text": "2026-08-17 · 11:30, 13:00, 18:30, 20:00",
    }
    assert normalizer.normalize_schedule(schedule) == []
    assert schedule["display_text"].endswith("11:30, 13:00, 18:30, 20:00")


def test_relative_dataset_path_has_stable_repo_label() -> None:
    assert normalizer.dataset_label(Path("agenda_web.json")) == "agenda_web.json"


def test_valpo_target_does_not_implicitly_include_gijon() -> None:
    targets = normalizer.dataset_targets(normalizer.DATASET_PATH)
    assert targets == [normalizer.DATASET_PATH]
    assert normalizer.GIJON_DATASET_PATH not in targets


def test_multicity_targeting_requires_explicit_opt_in() -> None:
    targets = normalizer.dataset_targets(normalizer.DATASET_PATH, include_sibling_cities=True)
    assert targets[0] == normalizer.DATASET_PATH
    if normalizer.GIJON_DATASET_PATH.exists():
        assert targets == [normalizer.DATASET_PATH, normalizer.GIJON_DATASET_PATH]


def test_public_projection_removes_editorial_recursively_and_is_idempotent() -> None:
    dataset = {
        "events": [
            {
                "id": "normal",
                "schedule": {"start": "2026-09-03T18:00:00-04:00"},
                "editorial": {"review": "private"},
                "provenance": {"evidence": [{"editorial": {"note": "private"}, "url": "https://example.test"}]},
            },
            {
                "id": "consolidated",
                "schedule": {"start": "2026-09-04T18:00:00-04:00"},
                "editorial": {"duplicate_sources": ["one"]},
                "image": {"url": "https://example.test/image.jpg"},
            },
            {
                "id": "corrected",
                "schedule": {"start": "2026-09-05T18:00:00-04:00"},
                "editorial": {"title_recovered": True},
                "links": {"official": "https://example.test/event"},
            },
        ]
    }
    projected, _, removed = normalizer.normalize_dataset(dataset)
    assert removed == 4
    assert "editorial" not in repr(projected)
    assert projected["events"][0]["provenance"]["evidence"][0]["url"] == "https://example.test"
    assert projected["events"][1]["image"]["url"].endswith("image.jpg")
    assert projected["events"][2]["links"]["official"].endswith("event")
    second, _, removed_again = normalizer.normalize_dataset(projected)
    assert second == projected
    assert removed_again == 0


def main() -> None:
    test_gallery_flattened_hours_become_ranges()
    test_artequin_flattened_hours_become_ranges()
    test_simple_two_clock_comma_becomes_interval()
    test_same_day_two_clock_comma_becomes_interval()
    test_start_only_is_not_given_an_invented_end()
    test_structured_multiple_sessions_are_preserved_in_gijon()
    test_rich_gijon_multiday_sessions_are_preserved()
    test_all_day_sentinel_becomes_date_only()
    test_opening_hours_separate_from_event_range()
    test_real_multiple_session_times_are_not_paired_without_timed_start()
    test_relative_dataset_path_has_stable_repo_label()
    test_valpo_target_does_not_implicitly_include_gijon()
    test_multicity_targeting_requires_explicit_opt_in()
    test_public_projection_removes_editorial_recursively_and_is_idempotent()
    print("SCHEDULE_PRESENTATION_NORMALIZER_TESTS_OK")


if __name__ == "__main__":
    main()
