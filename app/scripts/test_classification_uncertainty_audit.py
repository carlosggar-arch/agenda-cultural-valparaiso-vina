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

    # A guided visit describes format. It must not become training merely from
    # the words "visita guiada" when no thematic evidence says so.
    guided = build_event_semantics(item("Visita guiada al edificio histórico")["event"])
    assert guided["classification_state"] == "unclassified"
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

    # The concrete regressions that motivated the category repair must now be
    # strong, unambiguous decisions and therefore stay out of the review queue.
    known_cases = [
        {
            "id": "dire",
            "title": "Homenaje Dire Straits",
            "source_id": "camara_recinto_ferial_gijon",
            "source_name": "Cámara de Comercio de Gijón — Recinto Ferial y Palacio de Congresos",
            "primary_category": {"id": "otros", "label": "Otros panoramas"},
        },
        {
            "id": "showman",
            "title": "El Gran Showman",
            "source_id": "camara_recinto_ferial_gijon",
            "source_name": "Cámara de Comercio de Gijón — Recinto Ferial y Palacio de Congresos",
            "primary_category": {"id": "otros", "label": "Otros panoramas"},
        },
        {
            "id": "tiburones",
            "title": "Encuentro Educativo Tiburones",
            "source_id": "bioparc_acuario_gijon",
            "source_name": "BIOPARC Acuario de Gijón — Actividades y talleres",
            "primary_category": {"id": "otros", "label": "Otros panoramas"},
        },
    ]
    known_snapshot = build_uncertainty_snapshot(
        [{"city_id": "gijon", "event": event} for event in known_cases]
    )
    assert known_snapshot["summary"]["uncertain_count"] == 0

    baseline = {
        "source_metrics": {
            "gijon::fuente": {
                "city_id": "gijon",
                "source_name": "Fuente",
                "classified_events": 8,
                "uncertain_rate": 0.0,
            }
        }
    }
    current = {
        "source_metrics": {
            "gijon::fuente": {
                "city_id": "gijon",
                "source_name": "Fuente",
                "classified_events": 8,
                "uncertain_rate": 0.5,
            }
        }
    }
    risks = detect_uncertainty_anomalies(current, baseline)
    assert len(risks) == 1
    assert risks[0]["type"] == "uncertainty_rate_spike"
    assert risks[0]["severity"] == "critical"

    # Absolute risk still works when no historical baseline exists, so the
    # weekly read-only audit can identify systematically ambiguous sources.
    risks_without_baseline = detect_uncertainty_anomalies(current)
    assert len(risks_without_baseline) == 1
    assert risks_without_baseline[0]["type"] == "high_uncertainty_rate"

    print("CLASSIFICATION_UNCERTAINTY_AUDIT_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
