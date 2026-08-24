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

    # Generic source context can legitimately classify an event while leaving
    # only low confidence; the diagnostic must expose that rather than changing it.
    low = uncertainty_signals(
        build_event_semantics(
            item(
                "Actividad de agosto",
                "BIOPARC Acuario de Gijón — Actividades y talleres",
            )["event"]
        )
    )
    assert low["low_confidence"] is True
    assert low["uncertain"] is True

    snapshot = build_uncertainty_snapshot(
        [
            item("Concierto de jazz"),
            item("Taller de concierto"),
            item("Actividad de agosto", "BIOPARC Acuario de Gijón — Actividades y talleres"),
            item("Encuentro de agosto"),
        ]
    )
    assert snapshot["summary"]["total_events"] == 4
    assert snapshot["summary"]["classified_events"] == 3
    assert snapshot["summary"]["low_confidence_count"] == 1
    assert snapshot["summary"]["narrow_margin_count"] == 1
    assert snapshot["summary"]["uncertain_count"] == 2
    assert len(snapshot["review_queue"]) == 2

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
