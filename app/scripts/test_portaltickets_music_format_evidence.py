"""Sparse titles require event-format evidence, never a venue or artist allowlist."""
from __future__ import annotations
import copy
from datetime import date
import pytest
from refresh_portaltickets_editorial import (
    apply_detail, parse_detail_markup, parse_markup, refresh_dataset,
)
from scripts.public_category_rules import classify_public_category


def enriched_event(title: str, producer: str, description: str) -> dict:
    listing = f'''<h3>{title}</h3><p>6 de octubre 2026, 14:00</p>
    <p>Teatro Municipal de Viña del Mar, Viña del Mar</p>
    <a href="/evento/format-evidence">TICKETS AQUÍ</a>'''
    events, _ = parse_markup(listing, today=date(2026, 10, 2))
    assert len(events) == 1
    detail = parse_detail_markup(f'''<h4>Produce:</h4><p>{producer}</p>
    <h4>Descripción</h4><p>{description}</p><h4>POLÍTICAS DE REEMBOLSO</h4>''')
    before = copy.deepcopy(events[0])
    event = apply_detail(events[0], detail, verified_at="2026-10-02T15:49:39-03:00")
    assert event["id"] == before["id"]
    assert event["schedule"] == before["schedule"]
    assert event["location"] == before["location"]
    return event


@pytest.mark.parametrize("title,producer,description", [
    # Retained official ticket pages, fetched 2026-10-02; no title-specific rule.
    # https://www.portaldisc.com/evento/sigall50-semifinal
    ("SIGALL 50 — SEMIFINAL", "Espacio Cultural Viña del Mar",
     "Concurso Internacional de Ejecución Musical Sigall, mención Canto 2026."),
    # https://www.portaldisc.com/evento/elhambreylasganasdecomer
    ("CAMARA CHILENA DE LA DESTRUCCION + LA ESTRATEGIA DEL CARACOL", "Sello Leviatán",
     'Presentan su celebrado split "El hambre y las ganas de comer" en Valparaíso.'),
    ("Otra semifinal", "Organización independiente",
     "Concurso nacional de interpretación musical, con participantes invitados."),
    ("Dos proyectos invitados", "Sello Horizonte",
     "Los proyectos presentan su nuevo EP compartido ante el público local."),
])
def test_explicit_format_classifies_sparse_titles(title, producer, description):
    event = enriched_event(title, producer, description)
    assert classify_public_category(event)["category"]["id"] == "musica"
    assert event["description"] == description
    assert event["semantics"]["category_evidence_sources"]
    first, _ = refresh_dataset({"events": []}, [copy.deepcopy(event)], fetch_ok=True)
    second, _ = refresh_dataset(copy.deepcopy(first), [copy.deepcopy(event)], fetch_ok=True)
    assert first == second
    assert classify_public_category(second["events"][0])["category"]["id"] == "musica"


@pytest.mark.parametrize("producer,description", [
    ("Sello Horizonte", "Una jornada especial para encontrarnos en este espacio."),
    ("Sello Editorial Horizonte", "Presentan una nueva novela para lectores locales."),
    ("Empresa Horizonte", "Presentan su nuevo split de aire acondicionado."),
    ("Productora Horizonte", "La competencia comienza con la semifinal del certamen."),
    ("Espacio Cultural", "Una experiencia musical especial para compartir en comunidad."),
])
def test_insufficient_context_does_not_create_music_evidence(producer, description):
    event = enriched_event("Jornada especial", producer, description)
    assert not event["semantics"].get("category_evidence_sources")
    assert classify_public_category(event)["category"]["id"] != "musica"


def test_explicit_workshop_format_still_takes_precedence():
    event = enriched_event("Taller de preparación", "Espacio Cultural",
        "Preparación para el concurso internacional de ejecución musical.")
    assert classify_public_category(event)["category"]["id"] == "cursos-talleres-campus"
