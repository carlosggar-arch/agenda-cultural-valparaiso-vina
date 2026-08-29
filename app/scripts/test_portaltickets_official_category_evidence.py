from __future__ import annotations

from refresh_portaltickets_editorial import official_content_style_signal, parse_detail_markup


def test_related_official_content_exposes_reusable_music_evidence() -> None:
    detail = parse_detail_markup(
        '<h4>ARTISTAS Y TAGS RELACIONADOS</h4>'
        '<a href="/contenido/disco-banda-ejemplo-debut">Banda ejemplo</a>'
    )
    assert detail["related_content_urls"] == [
        "https://www.portaldisc.com/contenido/disco-banda-ejemplo-debut"
    ]
    signal = official_content_style_signal(
        '<h5>Estilo:</h5><div>Rock</div>',
        source_url=detail["related_content_urls"][0],
    )
    assert signal == {
        "kind": "official_related_content_style",
        "category": "musica",
        "value": "Rock",
        "source_url": "https://www.portaldisc.com/contenido/disco-banda-ejemplo-debut",
        "evidence_text": "musica estilo Rock",
    }


def test_untyped_related_content_is_not_category_evidence() -> None:
    assert official_content_style_signal(
        '<h5>Estilo:</h5><div>Contenido independiente</div>',
        source_url="https://www.portaldisc.com/contenido/actividad-ejemplo",
    ) is None


def main() -> None:
    test_related_official_content_exposes_reusable_music_evidence()
    test_untyped_related_content_is_not_category_evidence()
    print("PORTALTICKETS_OFFICIAL_CATEGORY_EVIDENCE_TESTS_OK")


if __name__ == "__main__":
    main()
