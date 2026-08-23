from __future__ import annotations

from audit_editorial_quality import audit_dataset, should_fail


def event(event_id: str, **overrides) -> dict:
    base = {
        "id": event_id,
        "title": f"Evento {event_id}",
        "event_type": "event",
        "content_kind": "dated_event",
        "primary_category": {"id": "musica", "label": "Música"},
        "categories": [{"id": "musica", "label": "Música"}],
        "schedule": {"start": "2026-08-24T19:00:00-04:00", "end": None, "occurrences": []},
        "location": {"venue": "Sala Central", "city": "Viña del Mar"},
        "source_url": "https://example.org/event",
        "links": {"official": "https://example.org/event"},
        "public_status": {"source_official": True, "information_completeness": "complete"},
        "image": {"url": f"https://example.org/{event_id}.jpg"},
    }
    base.update(overrides)
    return base


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["issues"]}


def test_clean_dataset_has_no_findings() -> None:
    report = audit_dataset({"events": [event("clean")]}, "valparaiso")
    assert report["issue_count"] == 0
    assert report["severity_counts"] == {"error": 0, "warning": 0, "info": 0}


def test_detects_structural_editorial_anomalies() -> None:
    broken = event(
        "broken",
        title="Título " * 25,
        primary_category={"id": "Música rara", "label": "Música"},
        categories=[{"id": "otra", "label": "Otra"}],
        schedule={"start": "2026-08-30", "end": "2026-08-20", "occurrences": []},
        location={"venue": "", "city": "Viña del Mar"},
        source_url="https://www.instagram.com/p/example/",
        links={"source": "https://www.instagram.com/p/example/"},
        public_status={"source_official": False, "information_completeness": "partial"},
    )
    report = audit_dataset({"events": [broken]}, "valparaiso")
    found = codes(report)
    assert "long_title" in found
    assert "malformed_category_id" in found
    assert "category_inconsistent" in found
    assert "missing_venue" in found
    assert "schedule_end_before_start" in found
    assert "social_only_unverified_source" in found
    assert should_fail(report, "error") is True


def test_detects_exhibition_date_incoherence() -> None:
    exhibition = event(
        "expo",
        primary_category={"id": "exposiciones", "label": "Exposiciones"},
        categories=[{"id": "exposiciones", "label": "Exposiciones"}],
        schedule={"start": "2026-09-10", "end": "2026-09-01", "occurrences": []},
    )
    report = audit_dataset({"events": [exhibition]}, "gijon")
    assert "exhibition_date_incoherent" in codes(report)


def test_detects_suspected_duplicates_and_repeated_images() -> None:
    shared_image = "https://example.org/shared.jpg?size=large"
    events = [
        event("a", title="Mismo evento", image={"url": shared_image}),
        event("b", title="Mismo evento", image={"url": shared_image}),
        event("c", title="Otro evento", image={"url": shared_image}),
    ]
    report = audit_dataset({"events": events}, "gijon")
    found = codes(report)
    assert "suspected_duplicate" in found
    assert "repeated_image" in found
    assert report["severity_counts"]["warning"] >= 2
    assert report["severity_counts"]["info"] == 3


def test_warning_threshold_is_optional() -> None:
    warning_only = event(
        "warning",
        source_url="https://www.instagram.com/p/example/",
        links={"source": "https://www.instagram.com/p/example/"},
        public_status={"source_official": False, "information_completeness": "partial"},
    )
    report = audit_dataset({"events": [warning_only]}, "gijon")
    assert should_fail(report, "error") is False
    assert should_fail(report, "warning") is True


def main() -> None:
    test_clean_dataset_has_no_findings()
    test_detects_structural_editorial_anomalies()
    test_detects_exhibition_date_incoherence()
    test_detects_suspected_duplicates_and_repeated_images()
    test_warning_threshold_is_optional()
    print("EDITORIAL_QUALITY_AUDIT_TESTS_OK")


if __name__ == "__main__":
    main()
