from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from production_semantic_capabilities import (
    assert_semantic_dataset_identity,
    select_gijon_semantic_case,
    select_valpo_semantic_cases,
    select_category_semantic_cases,
    assert_absent_category_inventory,
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
    def test_negative_probe_checks_both_surfaces_and_origins(self) -> None:
        from production_browser_selenium_smoke import verify_absent_semantic_categories
        driver = Mock()
        driver.execute_script.return_value = [{"id": "theatre", "category": "teatro"}]
        cases = [{"category_id": "literatura", "absence": True}]
        for origin in ("github-pages", "cloudflare"):
            for surface in ("app", "web"):
                verify_absent_semantic_categories(driver, origin, surface, cases)
                driver.execute_script.return_value = [{"id": "ghost", "category": "literatura"}]
                with self.assertRaisesRegex(SystemExit, "ABSENT_CATEGORY_RENDERED"):
                    verify_absent_semantic_categories(driver, origin, surface, cases)
                driver.execute_script.return_value = [{"id": "theatre", "category": "teatro"}]

    def test_present_capabilities_are_selected_from_canonical_fields(self) -> None:
        selected = select_valpo_semantic_cases(
            dataset(
                event("theatre-current", "teatro", end="2026-09-20"),
                event("literature-current", "literatura", end="2026-11-22"),
            ),
            reference=NOW,
        )
        self.assertEqual([row["category_id"] for row in selected], ["teatro", "literatura"])

    def test_display_title_uses_public_projection_and_retains_canonical_static_title(self) -> None:
        title = "Tata barahona & lsd – fotografías 15 años en teatro mauri SCD, Valparaíso"
        theatre = event("reviewed-concert", "teatro", end="2026-11-22", title=title)
        theatre["location"] = {"venue": "Teatro Mauri SCD, Valparaíso", "city": "Valparaíso"}
        selected = select_valpo_semantic_cases(
            dataset(theatre, event("book", "literatura", end="2026-11-22")), reference=NOW)
        self.assertEqual(selected[0]["title"], title)
        self.assertEqual(selected[0]["display_title"], "Tata barahona & lsd – fotografías 15 años")
        theatre["location"]["venue"] = "Otra sala"
        unrelated = select_valpo_semantic_cases(
            dataset(theatre, event("book", "literatura", end="2026-11-22")), reference=NOW)
        self.assertEqual(unrelated[0]["display_title"], title)

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

    def test_absent_category_requires_explicit_negative_case(self) -> None:
        selected = select_valpo_semantic_cases(
            dataset(event("theatre", "teatro", end="2026-11-22")), reference=NOW)
        self.assertEqual(selected[1], {
            "category_id": "literatura", "category_label": "Literatura", "absence": True})

    def test_generic_absence_contract_is_not_category_specific(self) -> None:
        selected = select_category_semantic_cases(
            dataset(event("other", "musica", end="2026-11-22")),
            {"musica": "Música", "seasonal": "Seasonal"}, default_timezone="UTC",
            reference=NOW, verify_absent=True)
        self.assertTrue(selected[1]["absence"])

    def test_shared_category_projection_selects_current_literature(self) -> None:
        book = event("book", "otros", end="2026-11-22", title="Presentación del libro nuevo")
        selected = select_valpo_semantic_cases(dataset(
            event("theatre", "teatro", end="2026-11-22"), book), reference=NOW)
        self.assertEqual(selected[1]["id"], "book")
        self.assertEqual(selected[1]["category_id"], "literatura")

    def test_date_only_start_valid_until_local_day_end(self) -> None:
        book = event("book", "literatura", end="", title="Presentación del libro nuevo")
        book["schedule"].update(start="2026-08-31", end=None, mode="dated")
        current = datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc)
        selected = select_valpo_semantic_cases(dataset(
            event("theatre", "teatro", end="2026-11-22"), book), reference=current)
        self.assertEqual(selected[1]["id"], "book")
        with self.assertRaisesRegex(SystemExit, "CAPABILITY_MISSING category=literatura"):
            select_valpo_semantic_cases(dataset(
                event("theatre", "teatro", end="2026-11-22"), book),
                reference=datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc))

    def test_empty_positive_coverage_fails_closed(self) -> None:
        with self.assertRaisesRegex(SystemExit, "NO_ACTIVE_CAPABILITIES"):
            select_valpo_semantic_cases(dataset(), reference=NOW)

    def test_expired_present_category_cannot_be_claimed_absent(self) -> None:
        with self.assertRaisesRegex(SystemExit, "CAPABILITY_MISSING category=literatura"):
            select_valpo_semantic_cases(dataset(
                event("theatre", "teatro", end="2026-11-22"),
                event("expired", "literatura", end="2026-08-28")), reference=NOW)

    def test_rendered_absent_category_fails_closed(self) -> None:
        absent = [{"category_id": "literatura", "absence": True}]
        assert_absent_category_inventory(absent, [{"id": "theatre", "category": "teatro"}])
        with self.assertRaisesRegex(SystemExit, "ABSENT_CATEGORY_RENDERED"):
            assert_absent_category_inventory(absent, [{"id": "ghost", "category": "literatura"}])

    def test_unclassified_inventory_cannot_prove_absence(self) -> None:
        with self.assertRaisesRegex(SystemExit, "CATEGORY_INVENTORY_INVALID"):
            assert_absent_category_inventory(
                [{"category_id": "literatura", "absence": True}], [{"id": "unknown", "category": ""}])

    def test_strict_selector_still_rejects_absence_by_default(self) -> None:
        with self.assertRaisesRegex(SystemExit, "CAPABILITY_MISSING"):
            select_gijon_semantic_case(dataset(), reference=NOW)

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
