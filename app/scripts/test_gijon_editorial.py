from datetime import date, timedelta

from fetch_gijon_xhtml import classify_editorial


def make_event(*, title: str, days: int, venue: str, category: str, tags=None, event_type="event") -> dict:
    start = date(2026, 8, 15)
    end = start + timedelta(days=days)
    return {
        "title": title,
        "event_type": event_type,
        "description": "",
        "primary_category": {"id": category, "label": category},
        "tags": tags or [],
        "schedule": {"start": start.isoformat(), "end": end.isoformat()},
        "location": {"venue": venue},
    }


def check(event: dict, expected: str) -> None:
    actual, reason = classify_editorial(event)
    assert actual == expected, f"expected {expected}, got {actual} ({reason}) for {event['title']}"


def main() -> None:
    check(
        make_event(
            title="Concierto de cámara",
            days=0,
            venue="Teatro Jovellanos",
            category="musica",
        ),
        "event",
    )
    check(
        make_event(
            title="Exposición temporal",
            days=35,
            venue="Centro de Cultura Antiguo Instituto",
            category="exposiciones",
        ),
        "event",
    )
    check(
        make_event(
            title="Cartelos n'asturianu (1976-2005)",
            days=221,
            venue="Muséu del Pueblu d'Asturies",
            category="exposiciones",
            tags=["Museos", "Exposición temporal"],
        ),
        "event",
    )
    check(
        make_event(
            title="Escena Amateur",
            days=800,
            venue="Gijón/Xixón",
            category="teatro",
            tags=["Super Evento (Programa)"],
            event_type="program",
        ),
        "program",
    )
    check(
        make_event(
            title="FETEN COMPAÑÍAS",
            days=7000,
            venue="Gijón/Xixón",
            category="teatro",
        ),
        "program",
    )
    check(
        make_event(
            title="Conoce el Muséu del Pueblu d'Asturies | Visitas comentadas",
            days=364,
            venue="Muséu del Pueblu d'Asturies",
            category="museos",
            tags=["Museos", "Turismo"],
        ),
        "flexible_offer",
    )
    print("Gijón editorial classification tests: OK")


if __name__ == "__main__":
    main()
