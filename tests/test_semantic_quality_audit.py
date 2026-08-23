from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.semantic_quality_audit import build_quality_snapshot, detect_source_anomalies


def item(city: str, source: str, event_id: str, title: str, category: str) -> dict:
    label = "Otros panoramas" if category == "otros" else "Música"
    return {
        "city_id": city,
        "event": {
            "id": event_id,
            "title": title,
            "source_name": source,
            "source_url": f"https://example.test/{source.lower().replace(' ', '-')}",
            "primary_category": {"id": category, "label": label},
        },
    }


def main() -> int:
    baseline = build_quality_snapshot([
        item("city-a", "Fuente A", f"old-{index}", f"Concierto de jazz {index}", "musica")
        for index in range(4)
    ])
    current = build_quality_snapshot([
        *[
            item("city-a", "Fuente A", f"now-{index}", f"Encuentro de agosto {index}", "otros")
            for index in range(4)
        ],
        *[
            item("city-a", "Fuente B", f"new-{index}", f"Actividad comunitaria {index}", "otros")
            for index in range(4)
        ],
        item("city-a", "Fuente C", "tiny-1", "Actividad comunitaria", "otros"),
    ])

    assert current["unclassified_count"] == 9
    assert len(current["unclassified_queue"]) == 9
    queue_item = current["unclassified_queue"][0]
    assert "candidates" in queue_item
    assert "evidence" in queue_item
    assert "source_name" in queue_item

    anomalies = detect_source_anomalies(current, baseline)
    anomaly_types = {(entry["source_name"], entry["type"]) for entry in anomalies}
    assert ("Fuente A", "unclassified_rate_spike") in anomaly_types
    assert ("Fuente A", "category_distribution_drift") in anomaly_types
    assert ("Fuente A", "dominant_category_shift") in anomaly_types
    assert ("Fuente B", "new_source_unclassified_rate") in anomaly_types
    assert not any(entry["source_name"] == "Fuente C" for entry in anomalies)
    assert any(entry["severity"] == "critical" for entry in anomalies)

    print("SEMANTIC_QUALITY_AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
