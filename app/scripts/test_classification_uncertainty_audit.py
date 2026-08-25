from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.classification_uncertainty_audit import (
    build_uncertainty_snapshot,
    detect_uncertainty_anomalies,
    uncertainty_signals,
)
from scripts.event_semantics import build_event_semantics


def item(title: str, source_name: str = "Fuente de prueba", **event_fields):
    event = {
        "id": event_fields.pop("id", title.casefold().replace(" ", "-")),
        "title": title,
        "source_name": source_name,
        "primary_category": {"id": "otros", "label": "Otros panoramas"},
        **event_fields,
    }
    return {"city_id": "gijon", "event": event}


def main() -> int:
    # Strong single-domain evidence remains outside the diagnostic queue.
    strong = uncertainty_signals(build_event_semantics(item("Concierto de jazz")["event"]))
    assert strong["uncertain"] is False

    # Two plausible domains with a 25-point difference are intentionally
    # reviewable even though the classifier still chooses one deterministically.
    close = uncertainty_signals(build_event_semantics(item("Taller de concierto")["event"]))
    assert close["narrow_margin"] is True
    assert close["margin"] == 25.0
    assert close["uncertain"] is True

    # BIOPARC's verified activities/workshops context is explicit source-id
    # evidence, never generic source-name text, and may remain low-confidence.
    low = uncertainty_signals(
        build_event_semantics(
            item(
                "Actividad de agosto",
                "BIOPARC Acuario de Gijón — Actividades y talleres",
                source_id="bioparc_acuario_gijon",
            )["event"]
        )
    )
    assert low["low_confidence"] is True
    assert low["uncertain"] is True

    snapshot = build_uncertainty_snapshot(
        [
            item("Concierto de jazz"),
            item("Taller de concierto"),
            item(
                "Actividad de agosto",
                "BIOPARC Acuario de Gijón — Actividades y talleres",
                source_id="bioparc_acuario_gijon",
            ),
            item("Encuentro de agosto"),
        ]
    )
    assert snapshot["summary"]["total_events"] == 4
    assert snapshot["summary"]["classified_events"] == 3
    assert snapshot["summary"]["low_confidence_count"] == 1
    assert snapshot["summary"]["narrow_margin_count"] == 1
    assert snapshot["summary"]["uncertain_count"] == 2
    assert len(snapshot["review_queue"]) == 2

    # Venue and boilerplate copied into a description are operational noise,
    # not semantic evidence for the event's public category.
    noise = build_event_semantics(
        item(
            "Encuentro de agosto",
            description="Teatro Municipal Comprar entradas",
            venue="Teatro Municipal",
        )["event"]
    )
    assert noise["classification_state"] == "unclassified"

    # A guided visit has two compatible semantic dimensions: it is a public
    # experience in the shared category taxonomy and a guided-visit format.
    # Keeping both assertions prevents the diagnostic from reviving the older
    # false dichotomy between thematic category and event format.
    guided = build_event_semantics(item("Visita guiada al edificio histórico")["event"])
    assert guided["classification_state"] == "classified"
    assert guided["primary_domain"] == "cursos-talleres-campus"
    assert guided["format"] == "visita-guiada"

    # Common but previously sparse music/stage wording should be useful domain
    # evidence without creating source-specific event patches.
    music = build_event_semantics(item("Nueva gira de la banda Aurora")["event"])
    assert music["primary_domain"] == "musica"
    stage = build_event_semantics(item("Noche de monólogo y magia")["event"])
    assert stage["primary_domain"] == "teatro"

    # Programs/catalogues are not individual events for classification-quality
    # diagnostics, while remaining valid semantic records for other consumers.
    program = build_event_semantics(
        item("Programación mensual de agosto", event_type="program")["event"]
    )
    assert program["event_kind"] == "program"
    assert program["diagnostic_eligible"] is False

    anomalies = detect_uncertainty_anomalies(snapshot)
    assert not anomalies["critical"]

    print("CLASSIFICATION_UNCERTAINTY_AUDIT_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
