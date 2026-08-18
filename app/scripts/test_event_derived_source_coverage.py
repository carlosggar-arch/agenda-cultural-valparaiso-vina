from __future__ import annotations

from datetime import date

from apply_event_derived_source_coverage import event_derived_coverage


def event(*, source_id: str, start: str, venue: str = "", organizer: str = "", venue_id: str = "", title: str = "Evento") -> dict:
    return {
        "title": title,
        "source_id": source_id,
        "schedule": {"start": start, "end": start},
        "location": {"venue": venue, "venue_id": venue_id},
        "organizer": organizer,
    }


def test_future_portaltickets_event_covers_casa_prisma() -> None:
    dataset = {"events": [event(source_id="portaltickets_valparaiso", start="2099-08-28", venue="Casa Prisma")]}
    result = event_derived_coverage(dataset, date(2099, 8, 18))
    assert result == {"casa_prisma_valpo": ["portaltickets_valparaiso"]}


def test_past_casa_prisma_event_does_not_cover_current_zero() -> None:
    dataset = {"events": [event(source_id="portaltickets_valparaiso", start="2099-08-01", venue="Casa Prisma")]}
    assert event_derived_coverage(dataset, date(2099, 8, 18)) == {}


def test_title_mention_alone_does_not_cover_la_paila() -> None:
    dataset = {"events": [event(
        source_id="some_aggregator",
        start="2099-08-28",
        venue="Otro Teatro",
        organizer="Otro Organizador",
        title="Conversatorio sobre Compañía La Paila",
    )]}
    assert event_derived_coverage(dataset, date(2099, 8, 18)) == {}


def test_exact_la_paila_organizer_creates_cross_source_coverage() -> None:
    dataset = {"events": [event(
        source_id="ticketing_provider",
        start="2099-08-28",
        venue="Sala invitada",
        organizer="Compañía La Paila",
    )]}
    result = event_derived_coverage(dataset, date(2099, 8, 18))
    assert result == {"compania_la_paila": ["ticketing_provider"]}


def test_own_source_is_not_cross_source_coverage() -> None:
    dataset = {"events": [event(source_id="casa_prisma_valpo", start="2099-08-28", venue="Casa Prisma Valpo")]}
    assert event_derived_coverage(dataset, date(2099, 8, 18)) == {}


def main() -> None:
    test_future_portaltickets_event_covers_casa_prisma()
    test_past_casa_prisma_event_does_not_cover_current_zero()
    test_title_mention_alone_does_not_cover_la_paila()
    test_exact_la_paila_organizer_creates_cross_source_coverage()
    test_own_source_is_not_cross_source_coverage()
    print("EVENT_DERIVED_SOURCE_COVERAGE_TESTS_OK")


if __name__ == "__main__":
    main()
