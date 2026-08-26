from __future__ import annotations

import json
from pathlib import Path

GUARD = Path("app/scripts/apply_content_quality_guard.py")
TESTS = Path("app/scripts/test_content_quality_guard.py")
DATASET = Path("agenda_web.json")
TARGET_ID = "agenda_7b8121a1ee3ce9d593a851ec"


def patch_guard() -> None:
    text = GUARD.read_text(encoding="utf-8")

    if "ADMIN_APPLICATION_ACTION = re.compile(" not in text:
        marker = "\nACTIVITY_NOUN = "
        addition = r'''

# Administrative application support is useful information, but it is not an
# attendance event. Keep this deliberately narrower than the generic
# submission-call rule: require an applicant-directed administrative action
# plus an explicit support resource, and never suppress a scheduled activity.
ADMIN_APPLICATION_ACTION = re.compile(
    r"\b(?:quieres|vas a|necesitas|puedes|debes)\s+(?:postular|solicitar)\b|"
    r"\b(?:solicita|solicitar|solicitudes?|postula|postulate)\b|"
    r"\b(?:se encuentra|esta)\s+abierta\s+la\s+convocatoria\b"
)
ADMIN_APPLICATION_SUPPORT = re.compile(
    r"\bcartas?\s+de\s+apoyo\b|"
    r"\brespaldo\s+(?:municipal|institucional)\b|"
    r"\bapoyo\s+(?:municipal|institucional)\s+(?:para|a)\s+(?:(?:tu|su|la)\s+)?postulacion\b"
)
'''
        if marker not in text:
            raise SystemExit("guard constants marker missing")
        text = text.replace(marker, addition + marker, 1)

    if "def is_administrative_application_support(event: dict) -> bool:" not in text:
        marker = "\ndef non_event_context_reason(event: dict) -> str | None:\n"
        addition = r'''

def is_administrative_application_support(event: dict) -> bool:
    if has_concrete_schedule(event):
        return False
    title = fold(event.get("title"))
    description = fold(event.get("description"))
    combined = f"{title} {description}".strip()
    return bool(
        ADMIN_APPLICATION_ACTION.search(combined)
        and ADMIN_APPLICATION_SUPPORT.search(combined)
    )
'''
        if marker not in text:
            raise SystemExit("guard function marker missing")
        text = text.replace(marker, addition + marker, 1)

    old = '''    if is_deadline_only_submission_call(event):
        return "call_for_submissions_deadline_not_event"
    if has_concrete_schedule(event):
'''
    new = '''    if is_deadline_only_submission_call(event):
        return "call_for_submissions_deadline_not_event"
    if is_administrative_application_support(event):
        return "administrative_application_support_not_event"
    if has_concrete_schedule(event):
'''
    if "administrative_application_support_not_event" not in text:
        if old not in text:
            raise SystemExit("guard reason marker missing")
        text = text.replace(old, new, 1)

    GUARD.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    if "def test_quarantines_administrative_application_support_without_event_schedule()" not in text:
        marker = "\ndef test_keeps_real_scheduled_activity_with_application_deadline() -> None:\n"
        addition = r'''

def test_quarantines_administrative_application_support_without_event_schedule() -> None:
    admin = event(
        id="fund-support-valpo",
        title="¿Quieres postular a los Fondos de Cultura 2027 y necesitas nuestra carta de apoyo?",
        location={"venue_id": None, "venue": "Valpo Cultura", "city": "Valparaíso"},
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Fecha por confirmar"},
        description="Ya se encuentra abierta la convocatoria para solicitar cartas de apoyo municipal. Este respaldo puede fortalecer tu propuesta.",
    )
    dataset = {"events": [admin], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"] == [{
        "id": "fund-support-valpo",
        "title": "¿Quieres postular a los Fondos de Cultura 2027 y necesitas nuestra carta de apoyo?",
        "reason": "administrative_application_support_not_event",
    }]


def test_quarantines_equivalent_application_support_in_another_city() -> None:
    admin = event(
        id="fund-support-gijon",
        title="¿Vas a postular a ayudas culturales y necesitas carta de apoyo?",
        location={"venue_id": None, "venue": "Centro Municipal", "city": "Gijón"},
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Fecha por confirmar"},
        description="Solicita una carta de apoyo institucional para tu postulación.",
    )
    dataset = {"events": [admin], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert dataset["events"] == []
    assert changes["quarantined"][0]["reason"] == "administrative_application_support_not_event"


def test_keeps_scheduled_information_session_about_applications() -> None:
    real = event(
        id="scheduled-funding-talk",
        title="Charla: Cómo postular a Fondos de Cultura 2027",
        schedule={"mode": "single", "start": "2026-09-03T18:00:00-04:00", "end": "2026-09-03T19:30:00-04:00", "occurrences": []},
        description="Sesión informativa para postular y solicitar cartas de apoyo. La charla se realizará el 03/09 a las 18:00.",
    )
    dataset = {"events": [real], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert [item["id"] for item in dataset["events"]] == ["scheduled-funding-talk"]
    assert changes["quarantined"] == []


def test_keeps_cultural_event_that_only_mentions_funding_support() -> None:
    real = event(
        id="funded-cultural-event",
        title="Concierto Nuevas Voces",
        schedule={"mode": "dated", "start": None, "end": None, "occurrences": [], "display_text": "Horario por confirmar"},
        description="Proyecto financiado por Fondos de Cultura y respaldado mediante una carta de apoyo municipal.",
    )
    dataset = {"events": [real], "counts": {"total": 1}}
    changes = apply_guard(dataset)
    assert [item["id"] for item in dataset["events"]] == ["funded-cultural-event"]
    assert changes["quarantined"] == []
'''
        if marker not in text:
            raise SystemExit("test insertion marker missing")
        text = text.replace(marker, addition + marker, 1)

    main_marker = '''    test_quarantines_description_led_submission_call_without_attendance_schedule()
    test_keeps_real_scheduled_activity_with_application_deadline()
'''
    main_replacement = '''    test_quarantines_description_led_submission_call_without_attendance_schedule()
    test_quarantines_administrative_application_support_without_event_schedule()
    test_quarantines_equivalent_application_support_in_another_city()
    test_keeps_scheduled_information_session_about_applications()
    test_keeps_cultural_event_that_only_mentions_funding_support()
    test_keeps_real_scheduled_activity_with_application_deadline()
'''
    if "    test_quarantines_administrative_application_support_without_event_schedule()\n" not in text:
        if main_marker not in text:
            raise SystemExit("test main marker missing")
        text = text.replace(main_marker, main_replacement, 1)

    TESTS.write_text(text, encoding="utf-8")


def materialize_dataset() -> None:
    from app.scripts.apply_content_quality_guard import (
        apply_guard,
        is_administrative_application_support,
    )

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    before_ids = {str(e.get("id") or "") for e in data.get("events", [])}
    matches = [
        e for e in data.get("events", [])
        if e.get("event_type") == "event" and is_administrative_application_support(e)
    ]
    match_ids = {str(e.get("id") or "") for e in matches}
    if TARGET_ID not in match_ids:
        raise SystemExit(f"target not recognized structurally; matches={sorted(match_ids)}")

    changes = apply_guard(data)
    after_ids = {str(e.get("id") or "") for e in data.get("events", [])}
    removed = before_ids - after_ids
    if removed != match_ids:
        raise SystemExit(
            f"unexpected collateral removal: semantic_matches={sorted(match_ids)} removed={sorted(removed)}"
        )
    if TARGET_ID in after_ids:
        raise SystemExit("target survived structural guard")

    DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ADMIN_NON_EVENT_MATERIALIZED", json.dumps({
        "matches": sorted(match_ids),
        "removed": sorted(removed),
        "total_after": data.get("counts", {}).get("total"),
        "events_after": data.get("counts", {}).get("events"),
        "quarantine_reasons": [q for q in changes.get("quarantined", []) if q.get("id") in match_ids],
    }, ensure_ascii=False))


if __name__ == "__main__":
    patch_guard()
    patch_tests()
    materialize_dataset()
