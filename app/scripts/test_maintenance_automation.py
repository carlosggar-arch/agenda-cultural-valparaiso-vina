from __future__ import annotations

import copy
from datetime import date

import audit_and_recover_images as images
import audit_source_coherence as coherence
import event_page_tools as tools
import parser_drift_guard as drift
import revalidate_upcoming_events as revalidate


def event(event_id="e1", title="Concierto Azul", source_id="s1", start="2099-08-20T20:00:00-04:00", venue="Sala Azul", image=None):
    return {
        "id": event_id,
        "title": title,
        "event_type": "event",
        "schedule": {"start": start, "end": start, "display_text": start},
        "location": {"city": "Valparaíso", "venue": venue, "address": "Calle 1"},
        "price": {"is_free": None, "currency": "CLP", "min_amount": None, "max_amount": None, "display_text": None},
        "links": {"official": "https://example.org/eventos/concierto-azul", "tickets": None, "source": None},
        "source_id": source_id,
        "source_name": "Fuente Uno",
        "public_status": {"cancelled": False, "sold_out": None},
        "image": {"url": image, "alt": title if image else None},
    }


def source_registry():
    return {
        "requirements": {
            "event_source_id_required": True,
            "event_source_must_be_registered": True,
            "new_public_source_requires_operational_mapping": True,
        },
        "name_aliases": {"Barrio Poniente Viña": "culturasvina"},
        "public_catalog_exceptions": {"Fuente Pública Legacy": "Pendiente de monitor operativo propio."},
    }


def jsonld_markup(name="Concierto Azul", start="2099-08-20T21:00:00-04:00", image="https://example.org/media/concierto.jpg", status="https://schema.org/EventScheduled", end=None):
    end = start if end is None else end
    return f'''<html><head><meta property="og:image" content="{image}"></head><body>
    <script type="application/ld+json">{{
      "@context":"https://schema.org","@type":"Event","name":"{name}",
      "startDate":"{start}","endDate":"{end}","eventStatus":"{status}",
      "location":{{"@type":"Place","name":"Sala Azul","address":{{"streetAddress":"Calle 2","addressLocality":"Valparaíso"}}}},
      "offers":{{"@type":"Offer","price":"5000","priceCurrency":"CLP","availability":"https://schema.org/InStock"}},
      "image":"{image}"
    }}</script></body></html>'''


def teatro_cartelera_markup():
    return '''<html><body>
      <div class="event"><span>Concierto</span><span>18.08 2026</span><span>20:00 hr</span><h2>Beyond</h2><p>Jakub Józef Orliński e Il Pomo d’Oro.</p></div>
      <div class="event"><span>19.08 2026</span><span>19:00 hr</span><h2>Armonías del Mundo en la Ciudad Jardín</h2></div>
    </body></html>'''


def test_event_match_and_detail_url():
    item = event()
    candidate, score = tools.best_matching_event(item, tools.extract_event_candidates(jsonld_markup()))
    assert candidate is not None
    assert score >= 0.9
    assert tools.event_detail_url(item) == "https://example.org/eventos/concierto-azul"
    social = event()
    social["links"]["official"] = "https://www.instagram.com/example/"
    social["source_url"] = "https://example.org/"
    assert tools.event_detail_url(social) is None


def test_revalidation_applies_only_confident_structured_changes():
    item = event()
    original_fetch = revalidate.fetch
    try:
        revalidate.fetch = lambda url: (True, 200, jsonld_markup(), None)
        updated, report = revalidate.build({"events": [item]}, date(2099, 8, 18), days=10, max_fetch=3)
    finally:
        revalidate.fetch = original_fetch
    changed = updated["events"][0]
    assert changed["schedule"]["start"].startswith("2099-08-20T21:00")
    assert changed["price"]["min_amount"] == 5000
    assert changed["location"]["address"].startswith("Calle 2")
    assert report["updated_events"] == 1


def test_teatro_vina_visible_schedule_overrides_conflicting_jsonld_time():
    item = event(title="Beyond", source_id="teatro_municipal_vina", start="2026-08-18T16:00:00-04:00", venue="Teatro Municipal de Viña del Mar")
    item["schedule"]["end"] = "2026-08-18"
    item["schedule"]["display_text"] = "18-08-2026 16:00 – 2026-08-18"
    item["links"]["official"] = "https://teatrovina.cl/evento/beyond/"
    item["source_url"] = "https://teatrovina.cl/"
    detail = jsonld_markup(name="Beyond", start="2026-08-18T16:00:00-04:00", end="2026-08-18")

    original_fetch = revalidate.fetch
    try:
        def fake_fetch(url):
            if url == revalidate.TEATRO_VINA_CARTELERA_URL:
                return True, 200, teatro_cartelera_markup(), None
            return True, 200, detail, None
        revalidate.fetch = fake_fetch
        updated, report = revalidate.build({"events": [item]}, date(2026, 8, 18), days=2, max_fetch=3)
    finally:
        revalidate.fetch = original_fetch

    changed = updated["events"][0]
    assert changed["schedule"]["start"] == "2026-08-18T20:00:00-04:00"
    assert changed["schedule"]["end"] == "2026-08-18"
    assert changed["schedule"]["display_text"] == "18-08-2026 · 20:00"
    assert changed["schedule"]["start_confidence"] == "official_visible_schedule"
    assert report["teatro_vina_cartelera"] == "ok"
    assert report["rows"][0]["visible_schedule_used"] is True


def test_teatro_vina_visible_schedule_requires_unique_title_date_time():
    ambiguous = '''<html><body>
      <span>09.08 2026</span><span>16:00 hr</span><h2>Fantasy Music Viña del Mar</h2>
      <span>09.08 2026</span><span>20:00 hr</span><h2>Fantasy Music Viña del Mar</h2>
    </body></html>'''
    assert revalidate.teatro_vina_visible_time(ambiguous, "Fantasy Music Viña del Mar", "2026-08-09") is None


def test_schedule_display_normalizes_same_day_date_only_end():
    assert revalidate.pretty_schedule("2026-08-18T20:00:00-04:00", "2026-08-18") == "18-08-2026 · 20:00"
    assert revalidate.pretty_schedule("2026-08-18T20:00:00-04:00", "2026-08-18T22:15:00-04:00") == "18-08-2026 · 20:00–22:15"


def test_cancelled_event_is_marked_not_deleted():
    item = event()
    markup = jsonld_markup(status="https://schema.org/EventCancelled")
    original_fetch = revalidate.fetch
    try:
        revalidate.fetch = lambda url: (True, 200, markup, None)
        updated, _ = revalidate.build({"events": [item]}, date(2099, 8, 18), days=10, max_fetch=3)
    finally:
        revalidate.fetch = original_fetch
    assert len(updated["events"]) == 1
    assert updated["events"][0]["public_status"]["cancelled"] is True


def test_parser_drift_restores_only_active_last_good_events():
    current = {"events": [], "counts": {}}
    coverage = {"cities": {"valparaiso-vina": {"sources": [
        {"id": "s1", "name": "Fuente Uno", "current_count": 0, "status": "zero_recent", "verified_inactive": False}
    ]}}}
    catalog = {"sources": [{"name": "Fuente Uno", "website_url": "https://example.org/agenda"}]}
    prior_event = event(start="2099-08-20T20:00:00-04:00")
    state = {"schema_version": "1.0.0", "sources": {"s1": {"last_good_count": 2, "events": [prior_event]}}}
    original_fetch = drift.fetch
    try:
        drift.fetch = lambda url: (True, 200, "<html></html>", None)
        updated, _, report = drift.build(current, coverage, catalog, state, date(2099, 8, 18))
    finally:
        drift.fetch = original_fetch
    assert len(updated["events"]) == 1
    assert updated["events"][0]["editorial"]["preserved_by_parser_drift_guard"] is True
    assert report["restored_events"] == 1

    expired = copy.deepcopy(state)
    expired["sources"]["s1"]["events"][0]["schedule"]["start"] = "2099-08-10"
    expired["sources"]["s1"]["events"][0]["schedule"]["end"] = "2099-08-10"
    original_fetch = drift.fetch
    try:
        drift.fetch = lambda url: (True, 200, "<html></html>", None)
        updated2, _, report2 = drift.build(current, coverage, catalog, expired, date(2099, 8, 18))
    finally:
        drift.fetch = original_fetch
    assert updated2["events"] == []
    assert report2["restored_events"] == 0


def test_source_coherence_detects_hard_duplicates_and_core_alignment():
    dataset = {"events": [event()]}
    coverage = {"cities": {"valparaiso-vina": {"sources": [{"id": "s1", "name": "Fuente Uno"}]}}}
    catalog = {"sources": [
        {"id": "fuente_1", "name": "Fuente Uno", "last_verified_at": "2099-08-01"},
        {"id": "fuente_1", "name": "Fuente Uno", "last_verified_at": "2099-08-01"},
    ]}
    report = coherence.build(dataset, coverage, catalog, date(2099, 8, 18), registry=source_registry())
    assert report["status"] == "critical"
    assert report["duplicate_public_ids"]
    assert report["duplicate_public_names"]


def test_source_coherence_uses_registry_aliases_and_exceptions():
    dataset = {"events": [event(source_id="culturasvina")]}
    coverage = {"cities": {"valparaiso-vina": {"sources": [
        {"id": "culturasvina", "name": "Culturas Viña"}
    ]}}}
    catalog = {"sources": [
        {"id": "fuente_barrio", "name": "Barrio Poniente Viña", "canonical_source_id": "barrio_poniente_vina", "last_verified_at": "2099-08-01"},
        {"id": "fuente_legacy", "name": "Fuente Pública Legacy", "last_verified_at": "2099-08-01"},
    ]}
    report = coherence.build(dataset, coverage, catalog, date(2099, 8, 18), registry=source_registry())
    assert report["status"] == "healthy"
    assert report["public_sources_missing_in_coverage"] == []
    assert report["summary"]["operational_aliases"] == 1
    assert report["summary"]["explicit_catalog_exceptions"] == 1
    assert report["summary"]["registry_state"] == "ok"


def test_source_coherence_requires_source_id_and_registry_contract():
    missing_id = {"events": [{"id": "e1", "source_name": "Fuente Uno"}]}
    empty_coverage = {"cities": {"valparaiso-vina": {"sources": []}}}
    empty_catalog = {"sources": []}
    report = coherence.build(missing_id, empty_coverage, empty_catalog, date(2099, 8, 18), registry=source_registry())
    assert report["status"] == "critical"
    assert report["unattributed_event_ids"] == ["e1"]

    broken = source_registry()
    broken["requirements"]["event_source_must_be_registered"] = False
    broken_report = coherence.build({"events": []}, empty_coverage, empty_catalog, date(2099, 8, 18), registry=broken)
    assert broken_report["status"] == "critical"
    assert broken_report["registry_contract_errors"] == ["event_source_must_be_registered"]


def test_image_recovery_uses_matched_event_page_only():
    item = event(image=None)
    original_fetch = images.fetch
    try:
        images.fetch = lambda url: (True, 200, jsonld_markup(), None)
        updated, report = images.build({"events": [item]}, date(2099, 8, 18), max_fetch=3)
    finally:
        images.fetch = original_fetch
    image = updated["events"][0]["image"]
    assert image["url"].endswith("concierto.jpg")
    assert image["relevance"] == "event_specific"
    assert report["recovered_event_specific_images"] == 1


def main():
    test_event_match_and_detail_url()
    test_revalidation_applies_only_confident_structured_changes()
    test_teatro_vina_visible_schedule_overrides_conflicting_jsonld_time()
    test_teatro_vina_visible_schedule_requires_unique_title_date_time()
    test_schedule_display_normalizes_same_day_date_only_end()
    test_cancelled_event_is_marked_not_deleted()
    test_parser_drift_restores_only_active_last_good_events()
    test_source_coherence_detects_hard_duplicates_and_core_alignment()
    test_source_coherence_uses_registry_aliases_and_exceptions()
    test_source_coherence_requires_source_id_and_registry_contract()
    test_image_recovery_uses_matched_event_page_only()
    print("MAINTENANCE_AUTOMATION_TESTS_OK")


if __name__ == "__main__":
    main()
