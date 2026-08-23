from __future__ import annotations

from semantic_quality_history import render_trend_markdown, report_fingerprint, update_history


def report(rate: float, dominant: str = "musica") -> dict:
    total = 10
    unclassified = int(round(rate * total))
    return {
        "summary": {
            "total_events": total,
            "unclassified_count": unclassified,
            "unclassified_rate": rate,
            "source_count": 1,
            "anomaly_count": 0,
            "critical_anomaly_count": 0,
        },
        "source_metrics": {
            "valparaiso::fuente": {
                "city_id": "valparaiso",
                "source_name": "Fuente",
                "source_url": "https://example.test",
                "total": total,
                "unclassified": unclassified,
                "unclassified_rate": rate,
                "category_distribution": {dominant: 1.0 - rate, "unclassified": rate},
                "dominant_category": dominant,
                "dominant_share": 1.0 - rate,
            }
        },
        "unclassified_queue": [],
        "source_anomalies": [],
    }


def main() -> int:
    first = report(0.1)
    history = update_history(first, None, "sha-a", "2026-08-23T10:00:00Z")
    assert len(history["snapshots"]) == 1

    # Same observable state does not manufacture a trend point; the canonical
    # producer reference advances on the existing last snapshot instead.
    same = update_history(first, history, "sha-b", "2026-08-23T11:00:00Z")
    assert len(same["snapshots"]) == 1
    assert same["snapshots"][-1]["source_ref"] == "sha-b"

    changed_report = report(0.4, "teatro")
    changed = update_history(changed_report, same, "sha-c", "2026-08-23T12:00:00Z")
    assert len(changed["snapshots"]) == 2
    assert changed["snapshots"][-1]["fingerprint"] == report_fingerprint(changed_report)
    markdown = render_trend_markdown(changed)
    assert "10.0% → 40.0%" in markdown
    assert "musica → teatro" in markdown

    trimmed = changed
    for index in range(5):
        trimmed = update_history(report((index + 5) / 10, "cine"), trimmed, f"sha-{index}", f"2026-08-23T1{index}:30:00Z", max_snapshots=3)
    assert len(trimmed["snapshots"]) == 3

    print("SEMANTIC_QUALITY_HISTORY_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
