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
        "source_id": "source-canonical",
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
        source_id=None,
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


def test_canonical_source_id_is_sufficient_provenance_for_social_event() -> None:
    canonical_social = event(
        "social-canonical",
        source_id="valpocultura",
        source_url="https://www.instagram.com/p/example/",
        links={"source": "https://www.instagram.com/p/example/"},
        public_status={"source_official": False, "information_completeness": "complete"},
    )
    report = audit_dataset({"events": [canonical_social]}, "valparaiso")
    assert "social_only_unverified_source" not in codes(report)


def test_detects_exhibition_date_incoherence() -> None:
    exhibition = event(
        "expo",
        primary_category={"id": "exposiciones", "label": "Exposiciones"},
        categories=[{"id": "exposiciones", "label": "Exposiciones"}],
        schedule={"start": "2026-09-10", "end": "2026-09-01", "occurrences": []},
    )
    report = audit_dataset({"events": [exhibition]}, "gijon")
    assert "exhibition_date_incoherent" in codes(report)


def test_detects_suspected_duplicates_and_unrelated_repeated_images() -> None:
    shared_image = "https://example.org/shared.jpg?size=large"
    events = [
        event("a", title="Mismo evento", source_id="a-source", location={"venue": "Sala A", "city": "Gijón"}, image={"url": shared_image}),
        event("b", title="Mismo evento", source_id="a-source", location={"venue": "Sala A", "city": "Gijón"}, image={"url": shared_image}),
        event("c", title="Otro evento", source_id="b-source", location={"venue": "Sala B", "city": "Gijón"}, image={"url": shared_image}),
    ]
    report = audit_dataset({"events": events}, "gijon")
    found = codes(report)
    assert "suspected_duplicate" in found
    assert "repeated_image" in found
    assert report["severity_counts"]["warning"] >= 2
    assert report["severity_counts"]["info"] == 3


def test_same_source_same_venue_representative_image_is_expected() -> None:
    shared = "https://example.org/venue.jpg"
    events = [
        event("a", title="Feria Shonen", image={"url": shared}),
        event("b", title="Yoga del sábado", image={"url": shared}),
        event("c", title="Invierno mágico", image={"url": shared}),
    ]
    report = audit_dataset({"events": events}, "valparaiso")
    assert "repeated_image" not in codes(report)


def test_same_series_poster_is_expected_across_sessions() -> None:
    shared = "https://example.org/festival.jpg"
    titles = [
        "Peor Imposible XXVII | Lunes 24 de agosto",
        "Peor Imposible XXVII | Martes 25 de agosto",
        "Peor Imposible XXVII | Miércoles 26 de agosto",
    ]
    events = [
        event(
            str(index),
            title=title,
            source_id="gijon_opendata_events",
            location={"venue": f"Sala {index}", "city": "Gijón"},
            image={"url": shared},
        )
        for index, title in enumerate(titles)
    ]
    report = audit_dataset({"events": events}, "gijon")
    assert "repeated_image" not in codes(report)


def test_known_provider_placeholder_is_not_reported_as_repeated_art() -> None:
    shared = "https://ciclismoasturiano.es/assets/smartweb/images/imgredes.jpg"
    events = [
        event("a", title="Trofeo A", location={"venue": "Lugar A", "city": "Gijón"}, image={"url": shared}),
        event("b", title="Trofeo B", location={"venue": "Lugar B", "city": "Gijón"}, image={"url": shared}),
        event("c", title="Trofeo C", location={"venue": "Lugar C", "city": "Gijón"}, image={"url": shared}),
    ]
    report = audit_dataset({"events": events}, "gijon")
    assert "repeated_image" not in codes(report)


def test_warning_threshold_is_optional() -> None:
    warning_only = event(
        "warning",
        source_id=None,
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
    test_canonical_source_id_is_sufficient_provenance_for_social_event()
    test_detects_exhibition_date_incoherence()
    test_detects_suspected_duplicates_and_unrelated_repeated_images()
    test_same_source_same_venue_representative_image_is_expected()
    test_same_series_poster_is_expected_across_sessions()
    test_known_provider_placeholder_is_not_reported_as_repeated_art()
    test_warning_threshold_is_optional()
    print("EDITORIAL_QUALITY_AUDIT_TESTS_OK")


if __name__ == "__main__":
    main()
