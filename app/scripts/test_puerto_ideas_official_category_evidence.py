"""Regression for six individually verified Puerto de Ideas 2026 talks.

The public category gate must not lose an officially reviewed talk if an
intermediate generic normalization has replaced the source category.
"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.public_category_rules import classify_public_category
TITLES=(
    "La arquitectura de la desinformación y la realidad sintética",
    "¿Cómo vivir con los otros? La amistad, la comunidad y la vida buena",
    "Las raíces del mal",
    "¿Qué buscamos cuando buscamos sentido?",
    "La máquina del olvido",
    "IA generativas",
)


def _event(title, source_id="puerto_de_ideas"):
    return {
        "source_id":source_id,
        "title":title,
        "primary_category":{"id":"otros","label":"Otros panoramas"},
        "categories":[{"id":"otros","label":"Otros panoramas"}],
        "description":None,
        "tags":["Puerto de Ideas 2026"],
    }


def test_six_exact_puerto_programme_talks_have_thematic_category():
    evidence=json.loads((ROOT/"shared/official-source-category-evidence.json").read_text(encoding="utf-8"))
    rules=[r for r in evidence["source_title_evidence"]
           if r["source_id"]=="puerto_de_ideas"]
    assert len(rules)==6
    for title in TITLES:
        outcome=classify_public_category(_event(title))
        assert outcome["category"]=={"id":"charlas-conferencias","label":"Charlas y conferencias"}
        assert outcome["confidence"]!="unclassified"
        assert any(x["kind"]=="source_title" and x["category"]=="charlas-conferencias"
                   for x in outcome["evidence"]),title


def test_different_source_or_unverified_title_cannot_borrow_category():
    for title in TITLES:
        outcome=classify_public_category(_event(title,"unrelated_festival"))
        assert not any(x["kind"]=="source_title" and x["category"]=="charlas-conferencias"
                       for x in outcome["evidence"])
    for title in ("Festival de ciencia", "Sinfonía de los mares",
                  "Encuentro de invierno", "IA", "La máquina"):
        outcome=classify_public_category(_event(title))
        assert not any(x["kind"]=="source_title" and x["category"]=="charlas-conferencias"
                       for x in outcome["evidence"])


def test_generated_web_module_retains_same_canonical_source_rules():
    generated=(ROOT/"app/public-category-taxonomy.generated.mjs").read_text(encoding="utf-8")
    assert "official_puerto_de_ideas_2026_individual_conference_programme_card" in generated
    assert "OFFICIAL_SOURCE_CATEGORY_EVIDENCE" in generated


if __name__=="__main__":
    test_six_exact_puerto_programme_talks_have_thematic_category()
    test_different_source_or_unverified_title_cannot_borrow_category()
    test_generated_web_module_retains_same_canonical_source_rules()
    print("PUERTO_IDEAS_CATEGORY_GUARD_OK")
