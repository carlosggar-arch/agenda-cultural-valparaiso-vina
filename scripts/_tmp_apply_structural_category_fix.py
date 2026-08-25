from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"PATCH_ANCHOR_MISSING: {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_taxonomy() -> None:
    path = ROOT / "shared/public-category-taxonomy.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rules = data["rules"]

    rules["tag_category_weight"] = 145
    rules["tag_category_aliases"] = {
        "musica": "musica",
        "musica clasica": "musica",
        "clasica": "musica",
        "concierto": "musica",
        "conciertos": "musica",
        "cine": "cine",
        "audiovisual": "cine",
        "teatro": "teatro",
        "danza": "teatro",
        "artes escenicas": "teatro",
        "exposicion": "exposiciones",
        "exposiciones": "exposiciones",
        "literatura": "literatura",
        "charla": "charlas-conferencias",
        "conferencia": "charlas-conferencias",
        "taller": "cursos-talleres-campus",
        "talleres": "cursos-talleres-campus",
    }

    for rule in rules["title_evidence"]:
        pattern = rule.get("pattern", "")
        if rule.get("category") == "teatro" and "musical|comedia musical|teatro musical" in pattern:
            rule["pattern"] = r"\b(?:comedia musical|teatro musical|obra musical|espectaculo musical)\b"
        elif rule.get("category") == "cine" and "largometraje|proyeccion" in pattern and "sing along" not in pattern:
            rule["pattern"] = pattern[:-3] + "|sing along)\\b"
        elif rule.get("category") == "musica" and "festival de musica" in pattern and "gospel" not in pattern:
            rule["pattern"] = pattern[:-3] + "|ensemble|gospel|choir|filarmonica|clasica|cuarteto|quartet|duo|trio|oratorio|cantata|sinfonia|sonata|acordeon|organetto)\\b"

    for rule in rules["description_evidence"]:
        pattern = rule.get("pattern", "")
        if rule.get("category") == "teatro" and "performance|funcion|musical" in pattern:
            rule["pattern"] = r"\b(?:teatro|teatral|danza|ballet|circo|escenicas|performance|funcion teatral|comedia musical|teatro musical|obra musical|espectaculo musical|monologo|stand up|humor|comedia|magia|ilusionismo|mago|maga|ilusionista)\b"
        elif rule.get("category") == "cine" and "largometraje|proyeccion" in pattern and "sing along" not in pattern:
            rule["pattern"] = pattern[:-3] + "|sing along)\\b"
        elif rule.get("category") == "musica" and "tocata|tocatas" in pattern and "gospel" not in pattern:
            rule["pattern"] = pattern[:-3] + "|ensemble|gospel|choir|filarmonica|clasica|cuarteto|quartet|duo|trio|oratorio|cantata|sinfonia|sonata|acordeon|organetto)\\b"

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def patch_python_classifier() -> None:
    path = ROOT / "scripts/public_category_rules.py"
    replace_once(
        path,
        'SEMANTIC_NOISE_PHRASES = tuple(RULES.get("semantic_noise_phrases", []))\n',
        'SEMANTIC_NOISE_PHRASES = tuple(RULES.get("semantic_noise_phrases", []))\n'
        'TAG_CATEGORY_WEIGHT = int(RULES.get("tag_category_weight", 0))\n'
        'TAG_CATEGORY_ALIASES = dict(RULES.get("tag_category_aliases", {}))\n',
    )
    replace_once(
        path,
        '\ndef _confidence_for_score(score: int) -> str:\n',
        '''\ndef _add_tag_category_evidence(\n    scores: dict[str, int],\n    evidence: list[dict[str, Any]],\n    event: dict[str, Any],\n) -> None:\n    if not TAG_CATEGORY_WEIGHT:\n        return\n    seen: set[tuple[str, str]] = set()\n    for raw_tag in event.get("tags") or []:\n        tag = fold(raw_tag)\n        category_id = TAG_CATEGORY_ALIASES.get(tag)\n        if not category_id or (category_id, tag) in seen:\n            continue\n        seen.add((category_id, tag))\n        _add_evidence(\n            scores, evidence, category_id, TAG_CATEGORY_WEIGHT, "source_tag", raw_tag\n        )\n\n\ndef _confidence_for_score(score: int) -> str:\n''',
    )
    replace_once(
        path,
        '    _add_source_title_evidence(scores, evidence, event)\n    _add_rule_evidence(\n',
        '    _add_tag_category_evidence(scores, evidence, event)\n    _add_source_title_evidence(scores, evidence, event)\n    _add_rule_evidence(\n',
    )


def patch_js_classifier() -> None:
    path = ROOT / "app/public-category-rules.mjs"
    replace_once(
        path,
        'const SEMANTIC_NOISE_PHRASES = RULES.semantic_noise_phrases || [];\n',
        'const SEMANTIC_NOISE_PHRASES = RULES.semantic_noise_phrases || [];\n'
        'const TAG_CATEGORY_WEIGHT = Number(RULES.tag_category_weight || 0);\n'
        'const TAG_CATEGORY_ALIASES = RULES.tag_category_aliases || {};\n',
    )
    replace_once(
        path,
        '\nfunction confidenceForScore(score) {\n',
        '''\nfunction addTagCategoryEvidence(scores, evidence, event) {\n  if (!TAG_CATEGORY_WEIGHT) return;\n  const seen = new Set();\n  for (const rawTag of event?.tags || []) {\n    const tag = foldPublicCategoryText(rawTag);\n    const categoryId = TAG_CATEGORY_ALIASES[tag];\n    const key = `${categoryId || ""}|${tag}`;\n    if (!categoryId || seen.has(key)) continue;\n    seen.add(key);\n    addEvidence(scores, evidence, categoryId, TAG_CATEGORY_WEIGHT, "source_tag", rawTag);\n  }\n}\n\nfunction confidenceForScore(score) {\n''',
    )
    replace_once(
        path,
        '  addSourceTitleEvidence(scores, evidence, event);\n  addRuleEvidence(\n',
        '  addTagCategoryEvidence(scores, evidence, event);\n  addSourceTitleEvidence(scores, evidence, event);\n  addRuleEvidence(\n',
    )


def add_regression_tests() -> None:
    py_path = ROOT / "app/scripts/test_public_category_regressions.py"
    py_path.write_text('''from __future__ import annotations\n\nimport json\nimport sys\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[2]\nif str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n\nfrom scripts.public_category_rules import classify_public_category, fold\n\n\ndef event(title, primary, *, tags=None, description="", venue=""):\n    return {\n        "title": title,\n        "primary_category": {"id": primary, "label": primary},\n        "categories": [{"id": primary, "label": primary}],\n        "tags": tags or [],\n        "description": description,\n        "location": {"venue": venue, "city": "Gijón"},\n    }\n\n\ndef category_id(value):\n    return classify_public_category(value)["category"]["id"]\n\n\ndef assert_case(name, value, expected):\n    actual = category_id(value)\n    if actual != expected:\n        raise AssertionError(f"{name}: expected {expected}, got {actual}")\n\n\ndef audit_current_datasets():\n    conflicts = []\n    expected_tag_categories = {\n        "musica": "musica",\n        "musica clasica": "musica",\n        "clasica": "musica",\n        "cine": "cine",\n    }\n    for rel in ("agenda_web.json", "app/data/gijon/agenda_web.json"):\n        payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))\n        for item in payload.get("events") or []:\n            expected = None\n            for tag in item.get("tags") or []:\n                expected = expected_tag_categories.get(fold(tag)) or expected\n            if not expected:\n                continue\n            actual = category_id(item)\n            if actual != expected:\n                conflicts.append((rel, item.get("title"), expected, actual, item.get("tags")))\n    if conflicts:\n        raise AssertionError("explicit source-tag category conflicts remain: " + repr(conflicts[:20]))\n\n\ndef main():\n    assert_case(\n        "Matriarcas",\n        event(\n            "Matriarcas: Poesía, Papel y Tinta",\n            "teatro",\n            description="Obra sobre Gabriela Mistral, Alfonsina Storni, poesía y literatura latinoamericana.",\n        ),\n        "teatro",\n    )\n    assert_case("DIFERENCIAS", event("'DIFERENCIAS', de ENSEMBLE DUOPLUS", "teatro", tags=["Música"]), "musica")\n    assert_case("GLORIA", event("¡GLORIA!", "teatro", tags=["Teatro Jovellanos", "Clásica"], venue="Teatro Jovellanos"), "musica")\n    assert_case("Mardi Jass Party", event("MARDI JASS PARTY | LOS GRANDES DEL GOSPEL", "teatro", tags=["Teatro Jovellanos", "Música"], venue="Teatro Jovellanos"), "musica")\n    assert_case("Spirits of New Orleans", event("SPIRITS OF NEW ORLEANS GOSPEL CHOIR | LOS GRANDES DEL GOSPEL", "teatro", tags=["Teatro Jovellanos", "Música"], venue="Teatro Jovellanos"), "musica")\n    assert_case(\n        "High School Musical Sing Along",\n        event(\n            "High School Musical Sing Along (2006)",\n            "cine",\n            tags=["Cine", "Función"],\n            description="Función confirmada por Cine Arte Viña del Mar. Categoría: Cine.",\n        ),\n        "cine",\n    )\n    assert_case("stage musical remains theatre", event("Comedia musical familiar", "cultura"), "teatro")\n    assert_case("venue does not define format", event("Concierto de cuarteto", "cultura", venue="Teatro Jovellanos"), "musica")\n    audit_current_datasets()\n    print("PUBLIC_CATEGORY_REGRESSIONS_OK")\n\n\nif __name__ == "__main__":\n    main()\n''', encoding="utf-8")

    js_path = ROOT / "app/public-category-regressions.test.mjs"
    js_path.write_text('''import assert from "node:assert/strict";\nimport { resolvePublicCategory } from "./public-category-rules.mjs";\n\nfunction event(title, primary, { tags = [], description = "", venue = "" } = {}) {\n  return {\n    title,\n    primary_category: { id: primary, label: primary },\n    categories: [{ id: primary, label: primary }],\n    tags,\n    description,\n    location: { venue, city: "Gijón" },\n  };\n}\n\nfunction expectCategory(name, value, expected) {\n  assert.equal(resolvePublicCategory(value).id, expected, name);\n}\n\nexpectCategory("Matriarcas", event(\n  "Matriarcas: Poesía, Papel y Tinta",\n  "teatro",\n  { description: "Obra sobre Gabriela Mistral, Alfonsina Storni, poesía y literatura latinoamericana." },\n), "teatro");\nexpectCategory("DIFERENCIAS", event("'DIFERENCIAS', de ENSEMBLE DUOPLUS", "teatro", { tags: ["Música"] }), "musica");\nexpectCategory("GLORIA", event("¡GLORIA!", "teatro", { tags: ["Teatro Jovellanos", "Clásica"], venue: "Teatro Jovellanos" }), "musica");\nexpectCategory("Mardi", event("MARDI JASS PARTY | LOS GRANDES DEL GOSPEL", "teatro", { tags: ["Teatro Jovellanos", "Música"], venue: "Teatro Jovellanos" }), "musica");\nexpectCategory("Spirits", event("SPIRITS OF NEW ORLEANS GOSPEL CHOIR | LOS GRANDES DEL GOSPEL", "teatro", { tags: ["Teatro Jovellanos", "Música"], venue: "Teatro Jovellanos" }), "musica");\nexpectCategory("High School Musical", event(\n  "High School Musical Sing Along (2006)",\n  "cine",\n  { tags: ["Cine", "Función"], description: "Función confirmada por Cine Arte Viña del Mar. Categoría: Cine." },\n), "cine");\nexpectCategory("stage musical", event("Comedia musical familiar", "cultura"), "teatro");\nexpectCategory("venue neutral", event("Concierto de cuarteto", "cultura", { venue: "Teatro Jovellanos" }), "musica");\nconsole.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");\n''', encoding="utf-8")


def add_materializer() -> None:
    path = ROOT / "scripts/materialize_public_categories.py"
    path.write_text('''from __future__ import annotations\n\nimport argparse\nimport json\nfrom pathlib import Path\n\nfrom scripts.public_category_rules import classify_public_category\n\nROOT = Path(__file__).resolve().parents[1]\nDEFAULT_DATASETS = (ROOT / "agenda_web.json", ROOT / "app/data/gijon/agenda_web.json")\n\n\ndef materialize(path: Path) -> tuple[int, int]:\n    payload = json.loads(path.read_text(encoding="utf-8"))\n    changed = 0\n    events = payload.get("events") or []\n    for event in events:\n        classification = classify_public_category(event)\n        category = dict(classification["category"])\n        before = (event.get("primary_category"), event.get("categories"))\n        event["primary_category"] = category\n        event["categories"] = [category]\n        semantics = event.get("semantics")\n        if isinstance(semantics, dict) and "canonical_category" in semantics:\n            semantics["canonical_category"] = category\n        after = (event.get("primary_category"), event.get("categories"))\n        if before != after:\n            changed += 1\n    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")\n    return len(events), changed\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description="Materialize the shared semantic public category into city datasets.")\n    parser.add_argument("paths", nargs="*", type=Path)\n    args = parser.parse_args()\n    paths = args.paths or list(DEFAULT_DATASETS)\n    for raw in paths:\n        path = raw if raw.is_absolute() else ROOT / raw\n        total, changed = materialize(path)\n        print(f"PUBLIC_CATEGORIES_MATERIALIZED path={path.relative_to(ROOT)} total={total} changed={changed}")\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n''', encoding="utf-8")


def patch_source_validation() -> None:
    path = ROOT / ".github/workflows/source-validation.yml"
    replace_once(
        path,
        '      - "scripts/classification_uncertainty_audit.py"\n',
        '      - "scripts/classification_uncertainty_audit.py"\n'
        '      - "scripts/public_category_rules.py"\n'
        '      - "scripts/materialize_public_categories.py"\n'
        '      - "shared/public-category-taxonomy.json"\n'
        '      - "app/public-category-rules.mjs"\n'
        '      - "app/public-category-taxonomy.generated.mjs"\n'
        '      - "app/public-category-regressions.test.mjs"\n'
        '      - "app/scripts/test_public_category_regressions.py"\n',
    )
    replace_once(
        path,
        '          python app/scripts/test_classification_uncertainty_audit.py\n',
        '          python app/scripts/test_classification_uncertainty_audit.py\n'
        '          python scripts/generate_public_category_module.py --check\n'
        '          python app/scripts/test_public_category_regressions.py\n'
        '          node app/public-category-regressions.test.mjs\n',
    )


def main() -> None:
    patch_taxonomy()
    patch_python_classifier()
    patch_js_classifier()
    add_regression_tests()
    add_materializer()
    patch_source_validation()
    print("STRUCTURAL_CATEGORY_PATCH_APPLIED")


if __name__ == "__main__":
    main()
