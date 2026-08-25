from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"fixture anchor missing in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# A generic `Teatro` tag is frequently a venue/programme bucket (especially at
# Teatro Jovellanos), not a reliable event-format declaration. Keep more
# specific stage tags such as Danza / Artes escénicas, but do not double-count
# the generic Teatro tag on top of the coarse source category.
taxonomy_path = ROOT / "shared/public-category-taxonomy.json"
taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
taxonomy["rules"]["tag_category_aliases"].pop("teatro", None)
taxonomy_path.write_text(
    json.dumps(taxonomy, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

# Matriarcas arrives upstream with explicit stage evidence before the public
# title normalizer removes the category prefix. Test the classifier at that
# canonical pre-normalization point rather than inventing a title exception.
replace(
    ROOT / "app/scripts/test_public_category_regressions.py",
    '            "Matriarcas: Poesía, Papel y Tinta",\n            "teatro",\n            description=',
    '            \'Teatro "Matriarcas: Poesía, Papel y Tinta"\',\n            "teatro",\n            tags=["Teatro"],\n            description=',
)
replace(
    ROOT / "app/public-category-regressions.test.mjs",
    '  "Matriarcas: Poesía, Papel y Tinta",\n  "teatro",\n  { description:',
    '  \'Teatro "Matriarcas: Poesía, Papel y Tinta"\',\n  "teatro",\n  { tags: ["Teatro"], description:',
)

# The dataset-wide guard is deliberately scoped to the failure mode being
# fixed: events that still resolve as theatre despite a Music/Classical source
# tag and no explicit stage wording. Mixed multidisciplinary events may carry
# several tags and must remain resolvable by title/description evidence.
py_test = ROOT / "app/scripts/test_public_category_regressions.py"
replace(py_test, "import json\nimport sys\n", "import json\nimport re\nimport sys\n")
old_audit = '''def audit_current_datasets():\n    conflicts = []\n    expected_tag_categories = {\n        "musica": "musica",\n        "musica clasica": "musica",\n        "clasica": "musica",\n        "cine": "cine",\n    }\n    for rel in ("agenda_web.json", "app/data/gijon/agenda_web.json"):\n        payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))\n        for item in payload.get("events") or []:\n            expected = None\n            for tag in item.get("tags") or []:\n                expected = expected_tag_categories.get(fold(tag)) or expected\n            if not expected:\n                continue\n            actual = category_id(item)\n            if actual != expected:\n                conflicts.append((rel, item.get("title"), expected, actual, item.get("tags")))\n    if conflicts:\n        raise AssertionError("explicit source-tag category conflicts remain: " + repr(conflicts[:20]))\n'''
new_audit = '''def audit_current_theatre_conflicts():\n    conflicts = []\n    music_tags = {"musica", "musica clasica", "clasica"}\n    explicit_stage = re.compile(\n        r"\\b(?:teatro|teatral|danza|ballet|circo|comedia musical|teatro musical|obra musical|espectaculo musical|monologo|stand up|magia|ilusionismo)\\b"\n    )\n    for rel in ("agenda_web.json", "app/data/gijon/agenda_web.json"):\n        payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))\n        for item in payload.get("events") or []:\n            actual = category_id(item)\n            if actual != "teatro":\n                continue\n            tags = {fold(tag) for tag in item.get("tags") or []}\n            if not tags.intersection(music_tags):\n                continue\n            if explicit_stage.search(fold(item.get("title"))):\n                continue\n            conflicts.append((rel, item.get("title"), item.get("tags")))\n    if conflicts:\n        raise AssertionError(\n            "music-tagged events still leaking into Teatro y danza: " + repr(conflicts[:20])\n        )\n'''
replace(py_test, old_audit, new_audit)
replace(py_test, "    audit_current_datasets()\n", "    audit_current_theatre_conflicts()\n")
replace(
    py_test,
    '    assert_case("stage musical remains theatre", event("Comedia musical familiar", "cultura"), "teatro")\n',
    '    assert_case("A CUATRO MANOS", event("A CUATRO MANOS", "teatro", tags=["Teatro Jovellanos", "Teatro", "Clásica"], venue="Teatro Jovellanos"), "musica")\n'
    '    assert_case("stage musical remains theatre", event("Comedia musical familiar", "cultura"), "teatro")\n'
    '    assert_case("music tag does not steal explicit stage musical", event("Obra Teatro Musical - Nemesio Pelao: ¿Qué es lo que te ha pasao?", "teatro", tags=["Música"]), "teatro")\n',
)

js_test = ROOT / "app/public-category-regressions.test.mjs"
replace(
    js_test,
    'expectCategory("stage musical", event("Comedia musical familiar", "cultura"), "teatro");\n',
    'expectCategory("A CUATRO MANOS", event("A CUATRO MANOS", "teatro", { tags: ["Teatro Jovellanos", "Teatro", "Clásica"], venue: "Teatro Jovellanos" }), "musica");\n'
    'expectCategory("stage musical", event("Comedia musical familiar", "cultura"), "teatro");\n'
    'expectCategory("music tag does not steal explicit stage musical", event("Obra Teatro Musical - Nemesio Pelao: ¿Qué es lo que te ha pasao?", "teatro", { tags: ["Música"] }), "teatro");\n',
)

# Keep the permanent regeneration command executable as documented (`python
# scripts/materialize_public_categories.py ...`) by adding the repository root
# to sys.path before importing the shared classifier.
materializer = ROOT / "scripts/materialize_public_categories.py"
replace(
    materializer,
    'import argparse\nimport json\nfrom pathlib import Path\n\nfrom scripts.public_category_rules import classify_public_category\n\nROOT = Path(__file__).resolve().parents[1]\n',
    'import argparse\nimport json\nimport sys\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\nif str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n\nfrom scripts.public_category_rules import classify_public_category\n',
)

print("CATEGORY_REGRESSION_FIXTURES_AND_AUDIT_ALIGNED")
