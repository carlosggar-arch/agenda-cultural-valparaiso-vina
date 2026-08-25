from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()
TAXONOMY = ROOT / "shared/public-category-taxonomy.json"
PY_REG = ROOT / "app/scripts/test_public_category_regressions.py"
JS_REG = ROOT / "app/public-category-regressions.test.mjs"
PORTAL_TEST = ROOT / "app/scripts/test_portaltickets_editorial.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"PATCH_MARKER_MISSING {label}")
    if text.count(old) != 1:
        raise SystemExit(f"PATCH_MARKER_NOT_UNIQUE {label} count={text.count(old)}")
    return text.replace(old, new, 1)


def patch_taxonomy() -> None:
    payload = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    rules = payload["rules"]
    genre_changed = False
    for rule in rules["description_evidence"]:
        pattern = str(rule.get("pattern") or "")
        if "rock|pop|soul|funk|indie|punk" in pattern:
            if int(rule.get("weight", 0)) < 35:
                rule["weight"] = 35
            genre_changed = True
            break
    if not genre_changed:
        raise SystemExit("DESCRIPTION_GENRE_RULE_NOT_FOUND")

    verified = [
        (r"\\bcarolina de la muela\\b", "verified_sparse_music_artist_portaltickets"),
        (r"\\bcalathea club\\b", "verified_sparse_electronic_music_series_portaltickets"),
        (r"\\bchaisen ?room\\b", "verified_sparse_music_series_portaltickets"),
        (r"\\bsofia alvez\\b", "verified_sparse_music_artist_portaltickets"),
        (r"\\bseba(?: y)? el monstruo\\b", "verified_sparse_music_artist_portaltickets"),
    ]
    existing = {(r.get("source_id"), r.get("category"), r.get("pattern")) for r in rules.get("source_title_evidence", [])}
    for pattern, reason in verified:
        key = ("portaltickets_valparaiso", "musica", pattern)
        if key in existing:
            continue
        rules.setdefault("source_title_evidence", []).append({
            "category": "musica",
            "pattern": pattern,
            "reason": reason,
            "source_id": "portaltickets_valparaiso",
            "weight": 120,
        })
    TAXONOMY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_python_regressions() -> None:
    text = PY_REG.read_text(encoding="utf-8")
    marker = "    audit_current_theatre_conflicts()\n"
    insertion = '''    assert_case(\n        "description genre alone reaches classification threshold",\n        event("Noche especial", "cultura", description="Una noche para bailar con clásicos del rock chileno."),\n        "musica",\n    )\n    for sparse_title in (\n        "Carolina de la Muela en El Pasaje",\n        "Aniversario Calathea Club",\n        "CHAISENROOM | NO BRANDING NO NATION",\n        "Sofía Alvez en El Pasaje",\n        "Seba & El Monstruo, lanzamiento: Lleno de 97",\n    ):\n        value = event(sparse_title, "cultura", city="Valparaíso")\n        value["source_id"] = "portaltickets_valparaiso"\n        assert_case(f"verified sparse PortalTickets music: {sparse_title}", value, "musica")\n    audit_current_theatre_conflicts()\n'''
    text = replace_once(text, marker, insertion, "python regression main")
    PY_REG.write_text(text, encoding="utf-8")


def patch_js_regressions() -> None:
    text = JS_REG.read_text(encoding="utf-8")
    marker = 'console.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");\n'
    insertion = '''expectCategory("description genre reaches threshold", event(\n  "Noche especial",\n  "cultura",\n  { description: "Una noche para bailar con clásicos del rock chileno." },\n), "musica");\nfor (const sparseTitle of [\n  "Carolina de la Muela en El Pasaje",\n  "Aniversario Calathea Club",\n  "CHAISENROOM | NO BRANDING NO NATION",\n  "Sofía Alvez en El Pasaje",\n  "Seba & El Monstruo, lanzamiento: Lleno de 97",\n]) {\n  expectCategory(`verified sparse PortalTickets music: ${sparseTitle}`, {\n    ...event(sparseTitle, "cultura", { city: "Valparaíso" }),\n    source_id: "portaltickets_valparaiso",\n  }, "musica");\n}\nconsole.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");\n'''
    text = replace_once(text, marker, insertion, "js regression end")
    JS_REG.write_text(text, encoding="utf-8")


def patch_portal_tests() -> None:
    text = PORTAL_TEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import copy\n",
        "import copy\nimport json\nimport sys\nfrom pathlib import Path\n",
        "portal imports",
    )
    text = replace_once(
        text,
        "from refresh_portaltickets_editorial import (\n",
        'ROOT = Path(__file__).resolve().parents[2]\nif str(ROOT) not in sys.path:\n    sys.path.insert(0, str(ROOT))\n\nfrom scripts.public_category_rules import classify_public_category\n\nfrom refresh_portaltickets_editorial import (\n',
        "portal root import",
    )
    marker = "\ndef main() -> None:\n"
    new_test = '''\ndef test_published_future_portaltickets_events_have_no_fallback_category() -> None:\n    payload = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))\n    reference_day = str(payload.get("generated_at") or payload.get("publication_date") or "")[:10]\n    pending = []\n    for item in payload.get("events") or []:\n        if str(item.get("source_id") or "") != SOURCE_ID:\n            continue\n        start_day = str((item.get("schedule") or {}).get("start") or "")[:10]\n        if reference_day and start_day and start_day < reference_day:\n            continue\n        resolved = classify_public_category(item)\n        if resolved["category"]["id"] == "unclassified":\n            pending.append((item.get("id"), item.get("title"), resolved.get("score")))\n    assert not pending, pending\n\n\ndef main() -> None:\n'''
    text = replace_once(text, marker, new_test, "portal main marker")
    marker_call = "    test_validator_rejects_legacy_crossed_record()\n"
    text = replace_once(
        text,
        marker_call,
        marker_call + "    test_published_future_portaltickets_events_have_no_fallback_category()\n",
        "portal test call",
    )
    PORTAL_TEST.write_text(text, encoding="utf-8")


def main() -> None:
    patch_taxonomy()
    patch_python_regressions()
    patch_js_regressions()
    patch_portal_tests()
    print("ZERO_VISIBLE_FALLBACK_PATCH_APPLIED")


if __name__ == "__main__":
    main()
