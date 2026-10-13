from __future__ import annotations

import pytest
import subprocess
import sys
import json
from pathlib import Path

from scripts.materialize_public_categories import materialize, migrate_payload
from scripts.materialize_public_categories import verify_projection_parity
from app.scripts.apply_content_quality_guard import is_generic_title, recover_generic_title


def event(category_id: str | None, label: str | None, *, description: str = "", city: str = "Valparaíso") -> dict:
    category = {"id": category_id, "label": label}
    return {
        "id": "agenda_fixture_1234567890abcdef",
        "title": "Actividad cultural",
        "event_type": "event",
        "schedule": {"start": "2026-08-29", "end": "2026-08-29"},
        "primary_category": category,
        "categories": [category],
        "description": description,
        "location": {"city": city},
        "source_id": "fixture_source",
        "links": {"official": "https://example.org/evento"},
    }


def migrate_one(row: dict) -> tuple[dict, dict]:
    return migrate_payload({"publication_date": "2026-08-28", "events": [row]})


def test_valid_canonical_category_is_preserved_idempotently() -> None:
    original = event("musica", "Música", description="Concierto de rock")
    once, report = migrate_one(original)
    twice, second = migrate_payload(once)
    assert once == twice
    assert report["counts"] == {"preserved": 1, "normalized": 0, "reclassified": 0, "excluded": 0, "blocked": 0}
    assert second["counts"]["preserved"] == 1


@pytest.mark.parametrize("city", ["Valparaíso", "Gijón"])
def test_materializer_converges_to_shared_classifier_even_for_thematic_input(city):
    from scripts.public_category_rules import resolve_public_category
    original = event("teatro", "Teatro", city=city)
    original["title"] = "Concierto sinfónico de primavera"
    migrated, report = migrate_one(original)
    current = migrated["events"][0]
    assert current["primary_category"] == resolve_public_category(original)
    assert current["primary_category"]["id"] == "musica"
    assert current["categories"] == [current["primary_category"]]
    twice, _ = migrate_payload(migrated)
    assert twice == migrated
    assert report["counts"]["reclassified"] == 1


@pytest.mark.parametrize("title", ["Presentación libros infantiles", "Presentación de libros de poesía", "Lanzamiento de los libros nuevos"])
def test_plural_book_presentations_are_materialized_without_source_exceptions(title):
    row = event("otros", "Otros panoramas")
    row["title"] = title
    migrated, report = migrate_one(row)
    assert migrated["events"][0]["primary_category"]["id"] == "literatura"
    assert report["counts"]["blocked"] == 0


@pytest.mark.parametrize(
    "title,description,expected_category",
    [
        (
            "Recorrido temático por el Museo // Muebles y herramientas de escritura",
            "Actividad oficial del museo.",
            "cursos-talleres-campus",
        ),
        ("Consort de Flautas Dulces UV", "Actividad oficial del museo.", "musica"),
        (
            "el arte de no saber», junto a la periodista Antonella Estévez",
            "El escritor participa en una conversación sobre la incertidumbre.",
            "charlas-conferencias",
        ),
    ],
)
def test_sparse_but_explicit_cultural_titles_are_classified_generically(
    title: str, description: str, expected_category: str
) -> None:
    row = event("otros", "Otros panoramas", description=description)
    row["title"] = title
    migrated, report = migrate_one(row)
    assert migrated["events"][0]["primary_category"]["id"] == expected_category
    assert report["counts"]["blocked"] == 0


def test_registered_current_exhibition_feed_classifies_sparse_artwork_titles() -> None:
    row = event("otros", "Otros panoramas")
    row.update(
        title="“Tierra florecida” de Concepción Balmes",
        source_id="sala_el_farol_uv",
    )
    row["links"]["official"] = "https://salaelfarol.uv.cl/muestra-actual"
    migrated, report = migrate_one(row)
    assert migrated["events"][0]["primary_category"]["id"] == "exposiciones"
    assert report["inventory"][0]["official_evidence"]["signals"] == [
        {
            "category": "exposiciones",
            "weight": 180,
            "kind": "source_title",
            "value": "registered_official_current_exhibition_feed",
        }
    ]

    unregistered = dict(row, source_id="unrelated_sparse_feed")
    unchanged, blocked = migrate_one(unregistered)
    assert unchanged["events"][0]["primary_category"]["id"] == "otros"
    assert blocked["counts"]["blocked"] == 1


def test_url_only_title_is_recovered_only_from_an_explicit_activity_phrase() -> None:
    row = event(
        "otros",
        "Otros panoramas",
        description=(
            "Acompáñanos en nuestro aniversario, donde celebraremos realizando el "
            "primer certamen internacional de Tunas UTFSM Valparaíso."
        ),
    )
    row["title"] = "https://forms.cloud.microsoft/r/i5Nfys6ZZ4"
    assert is_generic_title(row["title"])
    recovered, reason = recover_generic_title(row)
    assert recovered == "certamen internacional de Tunas UTFSM Valparaíso"
    assert reason == "explicit_activity_phrase_in_description"
    row["title"] = recovered
    migrated, report = migrate_one(row)
    assert migrated["events"][0]["primary_category"]["id"] == "musica"
    assert report["counts"]["blocked"] == 0

    ambiguous = dict(row, title="https://example.org/form", description="Información general.")
    assert recover_generic_title(ambiguous) == (None, None)


def test_category_receipt_retains_the_before_event_not_the_modified_category():
    from app.scripts.transformation_receipt_ledger import empty_ledger, make_receipt
    row = event("otros", "Otros panoramas", description="Concierto de jazz")
    ledger = empty_ledger()
    migrated, _ = migrate_payload({"publication_date": "2026-08-28", "events": [row]}, ledger=ledger)
    expected = make_receipt(stage="canonical_category_materializer", action="reclassification",
        reason="canonical_category_reclassified", source_event=row,
        canonical_event_id=row["id"], destination={"state": "published", "canonical_event_id": row["id"],
        "category": migrated["events"][0]["primary_category"]})
    receipt = ledger["receipts"][0]
    assert receipt["source_record_id"] == expected["source_record_id"]
    assert receipt["evidence"]["before_event"] == row
    assert receipt["evidence"]["after_event"] == migrated["events"][0]
    assert receipt["evidence"]["previous_category"] == row["primary_category"]


def test_actual_consumer_projection_drift_blocks_until_materialization():
    row = event("otros", "Otros panoramas", description="Concurso literario")
    payload = {"publication_date": "2026-08-28", "events": [row]}
    with pytest.raises(ValueError, match="PUBLIC_CATEGORY_PROJECTION_DIVERGENCE"):
        verify_projection_parity(payload)
    migrated, report = migrate_payload(payload)
    assert report["counts"]["blocked"] == 0
    verify_projection_parity(migrated)


def test_materialization_does_not_rewrite_a_cross_midnight_selection_day(tmp_path) -> None:
    payload = {"publication_date": "2026-09-21", "generated_at": "2026-09-22T00:04:11+02:00",
               "timezone": "Europe/Madrid", "selection_started_at": "2026-09-21T23:58:44+02:00",
               "counts": {"total": 1}, "events": [event("musica", "Música")]}
    payload["events"][0]["schedule"] = {"start": "2026-09-22T19:00:00+02:00"}
    assert payload["publication_date"] == "2026-09-21"
    payload["events"][0]["primary_category"] = {"id": "formacion-taller", "label": "Formación / taller"}
    migrated, _ = migrate_payload(payload)
    assert migrated["publication_date"] == payload["publication_date"]
    assert migrated["generated_at"] == payload["generated_at"]
    assert migrated["selection_started_at"] == payload["selection_started_at"]
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    materialize(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["publication_date"] == payload["publication_date"]
    assert saved["selection_started_at"] == payload["selection_started_at"]


def test_registered_alias_is_normalized() -> None:
    migrated, report = migrate_one(event("formacion-taller", "Formación / taller"))
    assert migrated["events"][0]["primary_category"]["id"] == "cursos-talleres-campus"
    assert report["counts"]["normalized"] == 1


@pytest.mark.parametrize("category_id,label", [("0", "0"), ("", ""), (None, None), ("unknown", "Desconocida")])
def test_invalid_category_with_no_evidence_remains_blocked(category_id: str | None, label: str | None) -> None:
    original = event(category_id, label)
    migrated, report = migrate_one(original)
    assert migrated == {"publication_date": "2026-08-28", "events": [original]}
    assert report["counts"]["blocked"] == 1
    assert report["inventory"][0]["official_evidence"]["url"] == "https://example.org/evento"


@pytest.mark.parametrize("legacy", ["otros", "actividad-panorama", "cultura"])
def test_legacy_fallback_is_reclassified_only_with_evidence_across_cities(legacy: str) -> None:
    for city in ("Valparaíso", "Gijón"):
        migrated, report = migrate_one(event(legacy, legacy, description="Concierto oficial de bandas de rock", city=city))
        assert migrated["events"][0]["primary_category"]["id"] == "musica"
        assert report["counts"]["reclassified"] == 1
        assert report["inventory"][0]["official_evidence"]["signals"]


def test_legacy_fallback_without_evidence_is_reported_not_guessed() -> None:
    migrated, report = migrate_one(event("cultura", "Cultura", city="Gijón"))
    assert migrated["events"][0]["primary_category"]["id"] == "cultura"
    assert report["counts"]["blocked"] == 1


def test_fail_closed_materialization_writes_report_but_not_partial_dataset(tmp_path) -> None:
    dataset = tmp_path / "agenda.json"
    report = tmp_path / "report.json"
    original = {"publication_date": "2026-08-28", "events": [event("otros", "Otros panoramas")]}
    dataset.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="PUBLIC_CATEGORY_MIGRATION_BLOCKED"):
        materialize(dataset, report_path=report, require_classified=True)
    assert json.loads(dataset.read_text(encoding="utf-8")) == original
    assert json.loads(report.read_text(encoding="utf-8"))["counts"]["blocked"] == 1


def test_cli_contract_success_reports_and_multi_dataset_failure_is_atomic(tmp_path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "materialize_public_categories.py"
    good = tmp_path / "good.json"
    blocked = tmp_path / "blocked.json"
    reports = tmp_path / "reports"
    ledger = tmp_path / "transformation-receipts.json"
    good_payload = {"publication_date": "2026-08-28", "events": [event("otros", "Otros", description="Concierto de jazz")]}
    blocked_payload = {"publication_date": "2026-08-28", "events": [event("otros", "Otros")]}
    good.write_text(json.dumps(good_payload), encoding="utf-8")
    blocked.write_text(json.dumps(blocked_payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "--contract", "shared-canonical-category-migration-v1", "--require-classified", "--report-dir", str(reports), "--ledger", str(ledger), str(good), str(blocked)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(good.read_text(encoding="utf-8")) == good_payload
    assert json.loads(blocked.read_text(encoding="utf-8")) == blocked_payload
    assert len(list(reports.glob("*.json"))) == 2

    success = subprocess.run(
        [sys.executable, str(script), "--contract", "shared-canonical-category-migration-v1", "--require-classified", "--ledger", str(ledger), str(good)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert success.returncode == 0
    assert json.loads(good.read_text(encoding="utf-8"))["events"][0]["primary_category"]["id"] == "musica"


def test_dated_event_disguised_as_program_cannot_escape_gate() -> None:
    row = event("otros", "Otros panoramas")
    row["event_type"] = "program"
    row["title"] = "Actividad fechada disfrazada"
    row["schedule"]["mode"] = "dated"
    _, report = migrate_one(row)
    assert report["counts"]["blocked"] == 1
    assert report["inventory"][0]["strict_gate_scope"] is True


def test_verified_generic_program_shell_is_not_a_future_event() -> None:
    row = event("otros", "Otros panoramas")
    row.update(event_type="program", title="Cartelera Agosto")
    row["schedule"]["mode"] = "multi_day"
    _, report = migrate_one(row)
    assert report["counts"]["blocked"] == 0
    assert report["inventory"][0]["strict_gate_scope"] is False


def test_long_running_event_remains_in_strict_scope() -> None:
    row = event("otros", "Otros panoramas")
    row["content_kind"] = "long_running_event"
    row["schedule"].update(mode="multi_day", start="2026-08-01", end="2026-10-01")
    _, report = migrate_one(row)
    assert report["counts"]["blocked"] == 1


@pytest.mark.parametrize(
    "title,description,reason",
    [
        ("Una estadía doble", "Participa, comparte y etiqueta para ganar una escapada para dos", "promotional_giveaway_not_attendance_event"),
    ],
)
def test_non_attendance_content_is_excluded_with_auditable_reason(title: str, description: str, reason: str) -> None:
    row = event("otros", "Otros panoramas", description=description)
    row["title"] = title
    migrated, report = migrate_one(row)
    assert migrated["events"] == []
    assert report["counts"]["excluded"] == 1
    assert report["inventory"][0]["action_reason"] == reason


def test_verified_literary_call_is_public_but_not_an_attendance_occurrence() -> None:
    row = event("otros", "Otros panoramas", description="Cierre de la segunda edición de SE BUSCA POETA. Convocatoria literaria para autores.")
    row["title"] = "Las bases en historia destacada !"
    row["public_status"] = {"source_official": True, "information_completeness": "complete"}
    row["schedule"].update(start="2026-09-30T23:59:00-04:00", end=None, occurrences=[])
    migrated, report = migrate_one(row)
    published = migrated["events"][0]
    assert published["title"] == "SE BUSCA POETA"
    assert published["content_kind"] == "call_for_submissions"
    assert published["submission"] == {"deadline": "2026-09-30", "attendance_occurrence": False}
    assert published["primary_category"]["id"] == "literatura"
    assert report["counts"]["reclassified"] == 1


def test_contaminated_multievent_is_excluded_and_never_becomes_category_blocker() -> None:
    row = event("otros", "Otros panoramas")
    row.update(
        title="Recital (Dominica 35, Recoleta)",
        description="Dos encuentros: el primerito el sábado. El segundito junto a otra persona Vi...",
        source_url="https://official.example/post",
    )
    row["location"] = {"city": "Valparaíso", "commune": "Valparaíso"}
    migrated, report = migrate_one(row)
    assert migrated["events"] == []
    assert report["counts"]["excluded"] == 1
    assert report["counts"]["blocked"] == 0
    assert report["inventory"][0]["action_reason"] == "multi_event_geography_conflict_with_truncated_segment"
