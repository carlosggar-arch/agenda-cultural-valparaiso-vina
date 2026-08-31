from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

from production_series_contract import (
    assert_dataset_identity,
    contract_has_future_occurrences,
    snapshot_from_bytes,
)


def snapshot(origin: str, events: list[dict[str, object]]) -> object:
    body = (json.dumps({"events": events}, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    return snapshot_from_bytes(origin, "data/gijon/agenda_web.json", f"https://{origin}.example/data.json", body)


def contract(*starts: str) -> dict[str, object]:
    return {
        "id": "fixture-series",
        "lifecycle": "active_occurrences",
        "timezone": "Europe/Madrid",
        "evidence_scope": {
            "source_id": "official-source",
            "venue": "Official venue",
            "official_host": "official.example",
            "ticket_host": "tickets.example",
        },
        "official_evidence": {
            "url": "https://official.example/program",
            "occurrences": [{"start": start} for start in starts],
        },
    }


def event(*starts: str, source_id: str = "official-source") -> dict[str, object]:
    return {
        "id": "canonical-series",
        "source_id": source_id,
        "location": {"venue": "Official venue"},
        "links": {
            "official": "https://official.example/program",
            "tickets": "https://tickets.example/program",
        },
        "schedule": {"occurrences": [{"start": start} for start in starts]},
    }


class ProductionSeriesContractTests(unittest.TestCase):
    def test_same_dataset_bytes_are_required_for_canonical_main_and_both_origins(self) -> None:
        events = [event("2030-09-01T19:00:00+02:00")]
        digest = assert_dataset_identity([snapshot("canonical-main", events), snapshot("pages", events), snapshot("cloudflare", events)])
        self.assertEqual(len(digest), 64)

    def test_different_origin_dataset_blocks_before_series_evaluation(self) -> None:
        with self.assertRaisesRegex(SystemExit, "PRODUCTION_SERIES_DATASET_DIVERGENCE"):
            assert_dataset_identity([snapshot("canonical-main", []), snapshot("pages", []), snapshot("cloudflare", [event("2030-09-01T19:00:00+02:00")])])

    def test_future_official_occurrence_missing_from_dataset_is_blocked(self) -> None:
        with self.assertRaisesRegex(SystemExit, "PRODUCTION_SERIES_FUTURE_OCCURRENCE_MISSING"):
            contract_has_future_occurrences(
                {"events": []},
                contract("2030-09-01T19:00:00+02:00"),
                now=datetime(2030, 8, 31, tzinfo=timezone.utc),
            )

    def test_expired_official_series_does_not_require_historical_cards(self) -> None:
        active, evidence_events, future_occurrences, latest = contract_has_future_occurrences(
            {"events": []},
            contract("2026-08-29T19:00:00+02:00", "2026-08-30T19:30:00+02:00"),
            now=datetime(2026, 8, 31, tzinfo=timezone.utc),
        )
        self.assertFalse(active)
        self.assertEqual(evidence_events, 0)
        self.assertEqual(future_occurrences, 0)
        self.assertEqual(latest, "2026-08-30T17:30:00+00:00")

    def test_many_to_one_series_fusion_preserves_all_future_occurrences(self) -> None:
        starts = ("2030-09-01T19:00:00+02:00", "2030-09-02T20:00:00+02:00")
        active, evidence_events, future_occurrences, _latest = contract_has_future_occurrences(
            {"events": [event(*starts)]},
            contract(*starts),
            now=datetime(2030, 8, 31, tzinfo=timezone.utc),
        )
        self.assertTrue(active)
        self.assertEqual(evidence_events, 1)
        self.assertEqual(future_occurrences, 2)

    def test_unrelated_source_cannot_satisfy_future_occurrence_evidence(self) -> None:
        start = "2030-09-01T19:00:00+02:00"
        with self.assertRaisesRegex(SystemExit, "PRODUCTION_SERIES_FUTURE_OCCURRENCE_MISSING"):
            contract_has_future_occurrences(
                {"events": [event(start, source_id="unrelated-source")]},
                contract(start),
                now=datetime(2030, 8, 31, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
