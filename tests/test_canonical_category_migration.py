from __future__ import annotations

import pytest
import subprocess
import sys
import json
from pathlib import Path

from scripts.materialize_public_categories import materialize, migrate_payload


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
    good_payload = {"publication_date": "2026-08-28", "events": [event("otros", "Otros", description="Concierto de jazz")]}
    blocked_payload = {"publication_date": "2026-08-28", "events": [event("otros", "Otros")]}
    good.write_text(json.dumps(good_payload), encoding="utf-8")
    blocked.write_text(json.dumps(blocked_payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "--contract", "shared-canonical-category-migration-v1", "--require-classified", "--report-dir", str(reports), str(good), str(blocked)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert json.loads(good.read_text(encoding="utf-8")) == good_payload
    assert json.loads(blocked.read_text(encoding="utf-8")) == blocked_payload
    assert len(list(reports.glob("*.json"))) == 2

    success = subprocess.run(
        [sys.executable, str(script), "--contract", "shared-canonical-category-migration-v1", "--require-classified", str(good)],
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
