from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.public_category_rules import classify_public_category, fold


def event(title, primary, *, tags=None, description="", venue=""):
    return {
        "title": title,
        "primary_category": {"id": primary, "label": primary},
        "categories": [{"id": primary, "label": primary}],
        "tags": tags or [],
        "description": description,
        "location": {"venue": venue, "city": "Gijón"},
    }


def category_id(value):
    return classify_public_category(value)["category"]["id"]


def assert_case(name, value, expected):
    actual = category_id(value)
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")


def audit_current_theatre_conflicts():
    conflicts = []
    music_tags = {"musica", "musica clasica", "clasica"}
    explicit_stage = re.compile(
        r"\b(?:teatro|teatral|danza|ballet|circo|comedia musical|teatro musical|obra musical|espectaculo musical|monologo|stand up|magia|ilusionismo)\b"
    )
    for rel in ("agenda_web.json", "app/data/gijon/agenda_web.json"):
        payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        for item in payload.get("events") or []:
            actual = category_id(item)
            if actual != "teatro":
                continue
            tags = {fold(tag) for tag in item.get("tags") or []}
            if not tags.intersection(music_tags):
                continue
            if explicit_stage.search(fold(item.get("title"))):
                continue
            conflicts.append((rel, item.get("title"), item.get("tags")))
    if conflicts:
        raise AssertionError(
            "music-tagged events still leaking into Teatro y danza: " + repr(conflicts[:20])
        )


def main():
    assert_case(
        "Matriarcas",
        event(
            'Teatro "Matriarcas: Poesía, Papel y Tinta"',
            "teatro",
            tags=["Teatro"],
            description="Obra sobre Gabriela Mistral, Alfonsina Storni, poesía y literatura latinoamericana.",
        ),
        "teatro",
    )
    assert_case("DIFERENCIAS", event("'DIFERENCIAS', de ENSEMBLE DUOPLUS", "teatro", tags=["Música"]), "musica")
    assert_case("GLORIA", event("¡GLORIA!", "teatro", tags=["Teatro Jovellanos", "Clásica"], venue="Teatro Jovellanos"), "musica")
    assert_case("Mardi Jass Party", event("MARDI JASS PARTY | LOS GRANDES DEL GOSPEL", "teatro", tags=["Teatro Jovellanos", "Música"], venue="Teatro Jovellanos"), "musica")
    assert_case("Spirits of New Orleans", event("SPIRITS OF NEW ORLEANS GOSPEL CHOIR | LOS GRANDES DEL GOSPEL", "teatro", tags=["Teatro Jovellanos", "Música"], venue="Teatro Jovellanos"), "musica")
    assert_case(
        "High School Musical Sing Along",
        event(
            "High School Musical Sing Along (2006)",
            "cine",
            tags=["Cine", "Función"],
            description="Función confirmada por Cine Arte Viña del Mar. Categoría: Cine.",
        ),
        "cine",
    )
    assert_case("A CUATRO MANOS", event("A CUATRO MANOS", "teatro", tags=["Teatro Jovellanos", "Teatro", "Clásica"], venue="Teatro Jovellanos"), "musica")
    assert_case("stage musical remains theatre", event("Comedia musical familiar", "cultura"), "teatro")
    assert_case("music tag does not steal explicit stage musical", event("Obra Teatro Musical - Nemesio Pelao: ¿Qué es lo que te ha pasao?", "teatro", tags=["Música"]), "teatro")
    assert_case("venue does not define format", event("Concierto de cuarteto", "cultura", venue="Teatro Jovellanos"), "musica")
    audit_current_theatre_conflicts()
    print("PUBLIC_CATEGORY_REGRESSIONS_OK")


if __name__ == "__main__":
    main()
