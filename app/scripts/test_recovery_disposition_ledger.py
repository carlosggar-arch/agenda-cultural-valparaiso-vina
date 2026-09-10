from __future__ import annotations

import copy
import unittest

from apply_content_quality_guard import apply_guard
from recovery_disposition_ledger import (
    ENVELOPE_FIELDS, append_recovery_dispositions, canonical_json_bytes,
    recovery_receipt_sha256, source_binding,
)
from transformation_receipt_ledger import empty_ledger, make_receipt


MOMENT = "2026-09-10T10:02:30+00:00"


def event(event_id: str, *, title: str = "Concierto de cámara", start: str = "2026-09-15T18:00:00-03:00") -> dict:
    url = f"https://www.instagram.com/p/{event_id}/"
    return {
        "id": event_id, "source_id": "cultural_venue", "title": title,
        "description": "Actividad cultural con evidencia.", "event_type": "event",
        "source_url": url, "links": {"source": url, "official": url},
        "location": {"city": "Valparaíso", "venue": "Sala cultural", "venue_id": "sala"},
        "schedule": {
            "mode": "dated", "start": start, "end": None,
            "occurrences": [{"start": start, "end": None, "evidence": {"kind": "explicit_pair"}}],
        },
        "primary_category": {"id": "musica", "label": "Música"},
        "categories": [{"id": "musica", "label": "Música"}],
    }


def recovery(item: dict, observation: str = "obs_example") -> dict:
    url = item["source_url"].rstrip("/")
    return {
        "stage": "finalizer_completeness_recovery", "action": "observation_recovery",
        "reason": "confirmed_observation_recovered_to_canonical_event",
        "source_record_id": observation, "source_id": "registered_account",
        "observation_id": observation, "canonical_event_id": item["id"],
        "occurrence_id": None, "source_url": url,
        "provenance": {"source_url": url, "method": "ledger_observation_exact_registry_identity"},
        "destination": {"state": "published", "canonical_event_id": item["id"]},
        "evidence": {"transformation_class": "recovered"},
    }


def fixture(item: dict) -> tuple[dict, dict]:
    dataset = {"events": [copy.deepcopy(item)], "publication_date": "2026-09-10", "generated_at": MOMENT}
    ledger = empty_ledger(generated_at=MOMENT)
    ledger["receipts"].append(recovery(item))
    return dataset, ledger


def dispositions(ledger: dict) -> list[dict]:
    return [row for row in ledger["receipts"] if row["action"] == "recovery_disposition"]


class RecoveryDispositionTests(unittest.TestCase):
    def test_retained_recovery_preserves_occurrences_without_terminal_evidence(self) -> None:
        item = event("retained")
        item["schedule"]["occurrences"].append({"start": "2026-09-15T21:00:00-03:00", "end": None})
        dataset, ledger = fixture(item)
        original = copy.deepcopy(ledger["receipts"])
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        self.assertEqual(dataset["events"][0]["schedule"], item["schedule"])
        self.assertEqual(ledger["receipts"], original)

    def test_candidate_quarantine_references_original_without_claiming_baseline_loss(self) -> None:
        item = event("new", title="Pronto…")
        dataset, ledger = fixture(item)
        original = copy.deepcopy(ledger["receipts"][0])
        changes = apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        self.assertEqual(dataset["events"], [])
        self.assertEqual(changes["quarantined"][0]["reason"], "generic_title_without_explicit_recovery")
        envelope = dispositions(ledger)[0]
        self.assertEqual(set(envelope), ENVELOPE_FIELDS)
        self.assertEqual(envelope["source_binding"], source_binding(item))
        self.assertEqual(envelope["recovery_receipt_sha256"], recovery_receipt_sha256(original))
        self.assertEqual(envelope["transformations"][0]["action"], "quarantine")
        self.assertEqual(envelope["transformations"][0]["reason"], changes["quarantined"][0]["reason"])
        self.assertIn(original, ledger["receipts"])
        self.assertEqual(len(ledger["receipts"]), 2)
        self.assertFalse(any(row["action"] == "quarantine" for row in ledger["receipts"]))

    def test_baseline_only_behavior_is_unchanged(self) -> None:
        item = event("baseline", title="Pronto…")
        dataset, ledger = fixture(item)
        ledger["receipts"] = []
        apply_guard(dataset, ledger=ledger, baseline_events=[item], generated_at=MOMENT)
        self.assertEqual(len(ledger["receipts"]), 1)
        self.assertEqual(ledger["receipts"][0]["action"], "quarantine")
        self.assertEqual(dispositions(ledger), [])

    def test_candidate_without_recovery_still_does_not_claim_baseline_loss(self) -> None:
        item = event("unrecovered", title="Pronto…")
        dataset, ledger = fixture(item)
        ledger["receipts"] = []
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        self.assertEqual(ledger["receipts"], [])

    def test_equivalent_deduplication_records_actual_survivor_and_initial_binding(self) -> None:
        duplicate = event("duplicate")
        survivor = event("canonical")
        survivor["description"] += " " * 100 + "Datos adicionales de la función."
        dataset, ledger = fixture(duplicate)
        dataset["events"].insert(0, survivor)
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        self.assertEqual([row["id"] for row in dataset["events"]], ["canonical"])
        envelope = dispositions(ledger)[0]
        self.assertEqual(envelope["source_binding"], source_binding(duplicate))
        operation = envelope["transformations"][0]
        self.assertEqual(operation["action"], "deduplication")
        self.assertEqual(operation["destination"], {"state": "merged", "canonical_event_id": "canonical"})
        self.assertEqual(operation["reason"], "same_source_title_venue_city_and_start")

    def test_distinct_functions_do_not_receive_false_dedup_evidence(self) -> None:
        item = event("early")
        late = event("late", start="2026-09-15T21:00:00-03:00")
        dataset, ledger = fixture(item)
        dataset["events"].append(late)
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        self.assertEqual(len(dataset["events"]), 2)
        self.assertEqual(dispositions(ledger), [])

    def test_repeated_guard_preserves_exact_bytes_and_receipt(self) -> None:
        item = event("repeated", title="Pronto…")
        dataset, ledger = fixture(item)
        original_dataset = copy.deepcopy(dataset)
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        expected = (canonical_json_bytes(dataset), canonical_json_bytes(ledger))
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        self.assertEqual(expected, (canonical_json_bytes(dataset), canonical_json_bytes(ledger)))
        apply_guard(original_dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        self.assertEqual(expected, (canonical_json_bytes(original_dataset), canonical_json_bytes(ledger)))

    def test_contradictory_repetition_blocks(self) -> None:
        item = event("contradiction", title="Pronto…")
        dataset, ledger = fixture(item)
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        changed = copy.deepcopy(item)
        changed["editorial"] = {
            "publication_review_required": True, "publication_review_reason": "missing_verified_date",
            "publication_review_missing_evidence": ["date"],
        }
        with self.assertRaisesRegex(ValueError, "RECOVERY_DISPOSITION_CONTRADICTORY_REPEAT"):
            apply_guard({"events": [changed]}, ledger=ledger, baseline_events=[], generated_at=MOMENT)

    def test_terminal_source_cannot_silently_reappear(self) -> None:
        item = event("resurrection", title="Pronto…")
        dataset, ledger = fixture(item)
        apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
        changed = copy.deepcopy(item)
        changed["title"] = "Concierto de cámara"
        with self.assertRaisesRegex(ValueError, "RECOVERY_DISPOSITION_CONTRADICTORY_REPEAT"):
            apply_guard({"events": [changed]}, ledger=ledger, baseline_events=[], generated_at=MOMENT)

    def test_crossed_recovery_source_blocks_without_raw_values_in_error(self) -> None:
        item = event("crossed", title="Pronto…")
        dataset, ledger = fixture(item)
        ledger["receipts"][0]["source_url"] = "https://example.invalid/another-post"
        with self.assertRaisesRegex(ValueError, "^RECOVERY_DISPOSITION_TRANSFORMATION_INVALID$"):
            apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)

    def test_unknown_envelope_field_and_crossed_observation_are_rejected(self) -> None:
        for tamper in (lambda row: row.update(unexpected=True), lambda row: row.update(observation_id="obs_other")):
            item = event("closed", title="Pronto…")
            dataset, ledger = fixture(item)
            apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)
            tamper(dispositions(ledger)[0])
            with self.assertRaisesRegex(ValueError, "RECOVERY_DISPOSITION_EXISTING_EVIDENCE_INVALID"):
                apply_guard(dataset, ledger=ledger, baseline_events=[], generated_at=MOMENT)

    def test_unexplained_disappearance_and_missing_survivor_are_rejected(self) -> None:
        item = event("missing")
        _, ledger = fixture(item)
        with self.assertRaisesRegex(ValueError, "RECOVERY_DISPOSITION_UNEXPLAINED_DISAPPEARANCE"):
            append_recovery_dispositions(ledger, before_events=[item], attempted_transformations=[], after_events=[])
        operation = make_receipt(
            stage="content_quality_guard", action="deduplication", reason="same_source_title_venue_city_and_start",
            source_event=item, canonical_event_id="missing-survivor",
            destination={"state": "merged", "canonical_event_id": "missing-survivor"},
        )
        with self.assertRaisesRegex(ValueError, "RECOVERY_DISPOSITION_SURVIVOR_INVALID"):
            append_recovery_dispositions(ledger, before_events=[item], attempted_transformations=[operation], after_events=[])

    def test_ambiguous_chain_cannot_create_authorizing_evidence(self) -> None:
        item = event("chain")
        _, ledger = fixture(item)
        operation = make_receipt(
            stage="content_quality_guard", action="quarantine",
            reason="generic_title_without_explicit_recovery", source_event=item,
            destination={"state": "quarantine", "canonical_event_id": None},
        )
        with self.assertRaisesRegex(ValueError, "RECOVERY_DISPOSITION_CHAIN_UNSUPPORTED"):
            append_recovery_dispositions(
                ledger, before_events=[item], attempted_transformations=[operation, copy.deepcopy(operation)], after_events=[],
            )
        self.assertEqual(dispositions(ledger), [])


def run_contract_tests() -> None:
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryDispositionTests))
    if not result.wasSuccessful():
        raise SystemExit("RECOVERY_DISPOSITION_CONTRACT_FAILED")


if __name__ == "__main__":
    run_contract_tests()
