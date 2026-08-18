from __future__ import annotations

import copy
from datetime import date

import refresh_valpocultura_zero_recovery as recovery


def future_year() -> int:
    return date.today().year + 1


def listing_markup(year: int) -> str:
    return f'''<section><time datetime="{year}-08-01">1 agosto</time><a href="/evento/centex-cartelera-agosto/">Centex - Cartelera Agosto</a></section>
    <section><time datetime="{year}-08-01">1 agosto</time><a href="/evento/valparaiso-profundo-programacion-agosto/">Valparaíso Profundo - Programación Agosto</a></section>
    <section><time datetime="{year}-08-03">3 agosto</time><a href="/evento/club-de-jazz-estrella-negra-cartelera-agosto/">Club de Jazz Estrella Negra - Cartelera Agosto</a></section>
    <section><time datetime="{year}-08-28">28 agosto</time><a href="/evento/casa-de-la-cultura-de-valparaiso-luciana-jury-en-chile/">Casa de la Cultura de Valparaíso - Luciana Jury en Chile</a></section>
    <section><time datetime="{year}-08-24">24 agosto</time><a href="/evento/teatro-municipal-cartelera-festival-internacional-de-cine-ojo-de-pescado/">Teatro Municipal - Cartelera Festival Internacional de Cine Ojo de Pescado</a></section>'''


def detail_markup(title: str, start: str, end: str | None = None, *, free: bool = True) -> str:
    final = f'<p>Finaliza: ({end})</p>' if end else ''
    free_text = '<p>Gratuito</p>' if free else '<p>Coste: $8.000</p>'
    return f'''<html><head><meta property="og:image" content="https://example.test/{start}.jpg"></head><body>
    <h1>{title}</h1><p>Inicio: ({start})</p>{final}{free_text}</body></html>'''


def test_discovery_and_conservative_publication() -> None:
    year = future_year()
    listing = listing_markup(year)
    found = recovery.discover(listing)
    assert {item["target"]["id"] for item in found} == {
        "centex", "valparaiso_profundo", "estrella_negra_jazz", "casa_cultura_valparaiso", "teatro_municipal_valparaiso"
    }

    details = {
        "centex-cartelera-agosto": detail_markup("Centex - Cartelera Agosto", f"{year}-08-01", f"{year}-08-31"),
        "valparaiso-profundo-programacion-agosto": detail_markup("Valparaíso Profundo - Programación Agosto", f"{year}-08-01", f"{year}-08-28"),
        "club-de-jazz-estrella-negra-cartelera-agosto": detail_markup("Club de Jazz Estrella Negra - Cartelera Agosto", f"{year}-08-03", f"{year}-08-29"),
        "casa-de-la-cultura-de-valparaiso-luciana-jury-en-chile": detail_markup("Casa de la Cultura de Valparaíso - Luciana Jury en Chile", f"{year}-08-28", None, free=False),
        "teatro-municipal-cartelera-festival-internacional-de-cine-ojo-de-pescado": detail_markup("Teatro Municipal - Cartelera Festival Internacional de Cine Ojo de Pescado", f"{year}-08-24", None),
    }
    original_fetch = recovery.fetch
    try:
        def fake_fetch(url: str):
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            return True, 200, details[slug], None
        recovery.fetch = fake_fetch
        rows = [recovery.detail(item, listing, date(year, 8, 18)) for item in found]
    finally:
        recovery.fetch = original_fetch

    by_id = {row["target"]["id"]: row for row in rows}
    assert by_id["centex"]["publishable"] is True
    assert by_id["valparaiso_profundo"]["publishable"] is True
    assert by_id["estrella_negra_jazz"]["publishable"] is True
    assert by_id["casa_cultura_valparaiso"]["publishable"] is True
    assert by_id["teatro_municipal_valparaiso"]["active"] is True
    assert by_id["teatro_municipal_valparaiso"]["publishable"] is False

    dataset, stats = recovery.refresh_dataset({"events": [], "counts": {}}, rows, fetch_ok=True)
    assert stats["published"] == 4
    assert dataset["counts"]["programs"] == 3
    assert dataset["counts"]["events"] == 1
    assert all((item.get("editorial") or {}).get("covered_source_ids") for item in dataset["events"])
    assert not any((item.get("location") or {}).get("venue_id") == "teatro_municipal_valparaiso" for item in dataset["events"])


def test_program_without_explicit_end_is_coverage_only() -> None:
    year = future_year()
    listing = f'<time datetime="{year}-08-01"></time><a href="/evento/centex-cartelera-agosto/">Centex - Cartelera Agosto</a>'
    candidate = recovery.discover(listing)[0]
    original_fetch = recovery.fetch
    try:
        recovery.fetch = lambda url: (True, 200, detail_markup("Centex - Cartelera Agosto", f"{year}-08-01", None), None)
        row = recovery.detail(candidate, listing, date(year, 8, 18))
    finally:
        recovery.fetch = original_fetch
    assert row["active"] is True
    assert row["publishable"] is False


def test_fetch_failure_preserves_previous_recovery() -> None:
    previous = {
        "id": "previous",
        "title": "Previous recovery",
        "event_type": "program",
        "schedule": {"start": "2099-01-01", "end": "2099-01-02"},
        "location": {"city": "Valparaíso"},
        "editorial": {"reason": recovery.RECOVERY_REASON, "covered_source_ids": ["centex"]},
    }
    dataset = {"events": [copy.deepcopy(previous)], "counts": {"total": 1, "events": 0, "courses": 0, "flexible_offers": 0, "programs": 1}}
    updated, stats = recovery.refresh_dataset(dataset, [], fetch_ok=False)
    assert updated["events"] == [previous]
    assert stats["preserved_previous"] is True


def main() -> None:
    test_discovery_and_conservative_publication()
    test_program_without_explicit_end_is_coverage_only()
    test_fetch_failure_preserves_previous_recovery()
    print("VALPOCULTURA_ZERO_RECOVERY_TESTS_OK")


if __name__ == "__main__":
    main()
