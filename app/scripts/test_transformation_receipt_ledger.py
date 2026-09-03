from __future__ import annotations

import copy

from apply_content_quality_guard import apply_guard
from transformation_receipt_ledger import append_receipt, empty_ledger, make_receipt


def event(event_id: str, title: str, *, start: str = "2026-09-01", venue: str = "Museo") -> dict:
    return {
        "id": event_id,
        "title": title,
        "description": "Exposición cultural con evidencia oficial.",
        "event_type": "event",
        "source_url": f"https://official.example/{event_id}",
        "links": {"official": f"https://official.example/{event_id}"},
        "schedule": {"mode": "single", "start": start, "end": None, "occurrences": []},
        "location": {"city": "Viña del Mar", "venue": venue, "venue_id": "museo"},
        "primary_category": {"id": "exposiciones", "label": "Exposiciones"},
        "categories": [{"id": "exposiciones", "label": "Exposiciones"}],
        "public_status": {"source_official": True},
        "provenance": {"title": {"source": "official_page"}},
    }


def test_append_only_and_idempotent_identity() -> None:
    ledger = empty_ledger()
    row = make_receipt(
        stage="quality", action="quarantine", reason="missing_evidence",
        source_event=event("one", "Pronto"), canonical_event_id=None,
    )
    assert append_receipt(ledger, row) is True
    assert append_receipt(ledger, copy.deepcopy(row)) is False
    assert len(ledger["receipts"]) == 1


def test_every_disappearance_has_receipt_and_merge_has_destination() -> None:
    first = event("canonical", "Exposición // Mar dulce", start="2026-09-01")
    second = event("duplicate", "Mar dulce", start="2026-09-01")
    dataset = {
        "generated_at": "2026-08-29T10:00:00-04:00",
        "publication_date": "2026-08-29",
        "events": [first, second],
        "counts": {"total": 2},
    }
    ledger = empty_ledger()
    changes = apply_guard(dataset, ledger=ledger, generated_at="2026-08-30T10:00:00-04:00")
    assert len(dataset["events"]) == 1
    receipt = next(row for row in ledger["receipts"] if row["action"] == "deduplication")
    assert receipt["source_record_id"] in {"canonical", "duplicate"}
    assert receipt["canonical_event_id"] == dataset["events"][0]["id"]
    assert receipt["destination"]["state"] == "merged"
    assert receipt["preserved_fields"]
    assert receipt["combined_provenance"]["sources"]
    assert changes["duplicates_consolidated"]


def test_generated_at_changes_only_when_semantic_content_changes() -> None:
    bad = event("bad", "Pronto…")
    bad["description"] = None
    bad["location"]["venue"] = None
    dataset = {
        "generated_at": "2026-08-29T10:00:00-04:00",
        "publication_date": "2026-08-29",
        "events": [bad],
        "counts": {"total": 1},
    }
    ledger = empty_ledger()
    apply_guard(dataset, ledger=ledger, generated_at="2026-08-30T10:00:00-04:00")
    assert dataset["generated_at"] == "2026-08-30T10:00:00-04:00"
    snapshot = copy.deepcopy(dataset)
    # A finalization injects one immutable effective timestamp into every stage.
    apply_guard(dataset, ledger=ledger, generated_at="2026-08-30T10:00:00-04:00")
    assert dataset == snapshot
    assert len(ledger["receipts"]) == 1


def test_exact_source_occurrence_merges_but_distinct_sources_do_not() -> None:
    first = event("first", "Taller textil", start="2026-09-01T15:00:00-04:00")
    second = event("second", "Taller textil", start="2026-09-01T15:00:00-04:00")
    for item in (first, second):
        item["primary_category"] = {"id": "cursos-talleres-campus", "label": "Cursos y talleres"}
        item["categories"] = [item["primary_category"]]
    first["source_id"] = second["source_id"] = "municipal_culture"
    second["schedule"]["end"] = "2026-09-01T16:30:00-04:00"
    other = event("other", "Taller textil", start="2026-09-01T15:00:00-04:00")
    other["primary_category"] = {"id": "cursos-talleres-campus", "label": "Cursos y talleres"}
    other["categories"] = [other["primary_category"]]
    other["source_id"] = "independent_venue"
    other["source_url"] = "https://another-authority.example/other"
    other["links"] = {"official": other["source_url"]}
    dataset = {
        "generated_at": "2026-08-30T10:00:00-04:00",
        "publication_date": "2026-08-30",
        "events": [first, second, other],
        "counts": {"total": 3},
    }
    ledger = empty_ledger()

    apply_guard(dataset, ledger=ledger, generated_at="2026-08-30T10:00:00-04:00")

    assert len(dataset["events"]) == 2
    receipt = next(row for row in ledger["receipts"] if row["action"] == "deduplication")
    assert receipt["reason"] == "same_source_title_venue_city_and_start"
    assert receipt["destination"]["canonical_event_id"] in {"first", "second"}
    assert any(item["id"] == "other" for item in dataset["events"])


def test_candidate_only_duplicate_does_not_claim_baseline_loss() -> None:
    canonical = event("canonical", "Taller textil", start="2026-09-01T15:00:00-04:00")
    duplicate = event("new-duplicate", "Taller textil", start="2026-09-01T15:00:00-04:00")
    dataset = {"publication_date": "2026-08-30", "events": [canonical, duplicate], "counts": {"total": 2}}
    ledger = empty_ledger()
    changes = apply_guard(dataset, ledger=ledger, baseline_events=[copy.deepcopy(canonical)])
    assert changes["duplicates_consolidated"]
    assert ledger["receipts"] == []


def test_valid_baseline_alias_points_to_retained_destination() -> None:
    canonical = event("canonical", "Taller textil", start="2026-09-01T15:00:00-04:00")
    alias = event("historical-alias", "Taller textil", start="2026-09-01T15:00:00-04:00")
    canonical["description"] += " Con información ampliada."
    dataset = {"publication_date": "2026-08-30", "events": [canonical, alias], "counts": {"total": 2}}
    ledger = empty_ledger()
    apply_guard(dataset, ledger=ledger, baseline_events=[copy.deepcopy(alias)])
    assert len(ledger["receipts"]) == 1
    assert ledger["receipts"][0]["source_record_id"] == "historical-alias"
    assert ledger["receipts"][0]["destination"]["canonical_event_id"] == "canonical"


def test_many_baseline_aliases_emit_many_to_one_receipts() -> None:
    canonical = event("canonical", "Taller textil", start="2026-09-01T15:00:00-04:00")
    canonical["description"] += " Registro canónico más completo."
    aliases = [event(f"alias-{index}", "Taller textil", start="2026-09-01T15:00:00-04:00") for index in (1, 2)]
    dataset = {"publication_date": "2026-08-30", "events": [canonical, *aliases], "counts": {"total": 3}}
    ledger = empty_ledger()
    apply_guard(dataset, ledger=ledger, baseline_events=copy.deepcopy(aliases))
    assert {row["source_record_id"] for row in ledger["receipts"]} == {"alias-1", "alias-2"}
    assert {row["canonical_event_id"] for row in ledger["receipts"]} == {"canonical"}


def main() -> None:
    test_append_only_and_idempotent_identity()
    test_every_disappearance_has_receipt_and_merge_has_destination()
    test_generated_at_changes_only_when_semantic_content_changes()
    test_exact_source_occurrence_merges_but_distinct_sources_do_not()
    test_candidate_only_duplicate_does_not_claim_baseline_loss()
    test_valid_baseline_alias_points_to_retained_destination()
    test_many_baseline_aliases_emit_many_to_one_receipts()
    print("TRANSFORMATION_RECEIPT_LEDGER_TESTS_OK")


if __name__ == "__main__":
    main()
