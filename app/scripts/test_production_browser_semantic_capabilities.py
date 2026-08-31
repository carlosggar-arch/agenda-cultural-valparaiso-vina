from __future__ import annotations

from datetime import datetime, timezone
import unittest

from production_semantic_capabilities import (
    assert_semantic_dataset_identity,
    select_gijon_semantic_case,
    select_valpo_semantic_cases,
)


NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)


def event(event_id: str, category: str, *, end: str, title: str | None = None) -> dict[str, object]:
    return {
        "id": event_id,
        "title": title or f"Canonical {category}",
        "event_type": "event",
        "primary_category": {"id": category, "label": category.title()},
        "source_id": "official-source",
        "links": {"official": "https://official.example/event"},
        "schedule": {
            "mode": "multi_day",
            "start": "2026-08-01T10:00:00-04:00",
            "end": end,
            "timezone": "America/Santiago",
            "occurrences": [],
        },
    }


def dataset(*events: dict[str, object]) -> dict[str, object]:
    return {"generated_at": "2026-08-31T00:00:00Z", "events": list(events)}


class ProductionBrowserSemanticCapabilityTests(unittest.TestCase):
    def test_present_capabilities_are_selected_from_canonical_fields(self) -> None:
        selected = select_valpo_semantic_cases(
            dataset(
                event("theatre-current", "teatro", end="2026-09-20"),
                event("literature-current", "literatura", end="2026-11-22"),
            ),
            reference=NOW,
        )
        self.assertEqual([row["category_id"] for row in selected], ["teatro", "literatura"])

    def test_expired_fixture_is_replaced_by_valid_current_capability(self) -> None:
        selected = select_valpo_semantic_cases(
            dataset(
                event("expired-historical-id", "teatro", end="2026-08-28"),
                event("current-replacement", "teatro", end="2026-09-20"),
                event("literature-current", "literatura", end="2026-11-22"),
            ),
            reference=NOW,
        )
        self.assertEqual(selected[0]["id"], "current-replacement")

    def test_absent_capability_fails_closed(self) -> None:
        with self.assertRaisesRegex(SystemExit, "PRODUCTION_VALPO_SEMANTIC_CAPABILITY_MISSING category=teatro"):
            select_valpo_semantic_cases(
                dataset(event("literature-current", "literatura", end="2026-11-22")),
                reference=NOW,
            )

    def test_divergent_datasets_fail_closed(self) -> None:
        with self.assertRaisesRegex(SystemExit, "PRODUCTION_SEMANTIC_DATASET_DIVERGENCE"):
            assert_semantic_dataset_identity({"github-pages": b'{"events":[]}', "cloudflare": b'{"events":[1]}'})

    def test_changed_id_with_same_semantics_remains_selectable(self) -> None:
        before = select_valpo_semantic_cases(
            dataset(
                event("old-id", "teatro", end="2026-09-20", title="Canonical theatre"),
                event("literature-old", "literatura", end="2026-11-22"),
            ),
            reference=NOW,
        )
        after = select_valpo_semantic_cases(
            dataset(
                event("new-id", "teatro", end="2026-09-20", title="Canonical theatre"),
                event("literature-new", "literatura", end="2026-11-22"),
            ),
            reference=NOW,
        )
        self.assertEqual(before[0]["title"], after[0]["title"])
        self.assertNotEqual(before[0]["id"], after[0]["id"])

    def test_unverified_source_cannot_satisfy_capability(self) -> None:
        theatre = event("unverified", "teatro", end="2026-09-20")
        theatre["links"] = {"official": ""}
        with self.assertRaisesRegex(SystemExit, "PRODUCTION_VALPO_SEMANTIC_CAPABILITY_MISSING category=teatro"):
            select_valpo_semantic_cases(
                dataset(theatre, event("literature-current", "literatura", end="2026-11-22")),
                reference=NOW,
            )

    def test_expired_gijon_fixture_is_replaced_by_current_exhibition(self) -> None:
        selected = select_gijon_semantic_case(
            dataset(
                event("expired-installation", "exposiciones", end="2026-08-30"),
                event("current-exhibition", "exposiciones", end="2026-10-30"),
            ),
            reference=NOW,
        )
        self.assertEqual(selected["id"], "current-exhibition")


if __name__ == "__main__":
    unittest.main()
