from __future__ import annotations

import argparse
import json
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found: {path}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply() -> None:
    # Keep long, source-derived semantic evidence separately from the short public
    # description so re-materialization is deterministic without synthetic tags.
    replace_once(
        "scripts/public_category_rules.py",
        'def description_evidence_text(event: dict[str, Any]) -> str:\n    values = [event.get("description"), *(event.get("tags") or [])]\n',
        'def description_evidence_text(event: dict[str, Any]) -> str:\n    semantics = event.get("semantics") if isinstance(event.get("semantics"), dict) else {}\n    values = [semantics.get("category_evidence_text"), event.get("description"), *(event.get("tags") or [])]\n',
    )
    replace_once(
        "app/public-category-rules.mjs",
        'function descriptionEvidenceText(event) {\n  return stripSemanticNoise([\n    event?.description,\n    ...(event?.tags || []),\n',
        'function descriptionEvidenceText(event) {\n  return stripSemanticNoise([\n    event?.semantics?.category_evidence_text,\n    event?.description,\n    ...(event?.tags || []),\n',
    )
    replace_once(
        "app/scripts/refresh_portaltickets_editorial.py",
        '    semantic_text = str(detail.get("semantic_text") or description or "").strip()\n    classification_event = dict(event)\n',
        '    semantic_text = str(detail.get("semantic_text") or description or "").strip()\n    semantics = event.setdefault("semantics", {})\n    if semantic_text:\n        semantics["category_evidence_text"] = semantic_text\n    else:\n        semantics.pop("category_evidence_text", None)\n    classification_event = dict(event)\n',
    )

    # Regression: semantic source evidence must remain available independently of
    # the shortened public description and must not be converted into a category tag.
    replace_once(
        "app/scripts/test_portaltickets_editorial.py",
        '    assert enriched["primary_category"] == {"id": "musica", "label": "Música"}\n    assert enriched["tags"] == ["PortalTickets"]\n\n\n',
        '    assert enriched["primary_category"] == {"id": "musica", "label": "Música"}\n    assert enriched["tags"] == ["PortalTickets"]\n    assert "música chilena" in enriched["semantics"]["category_evidence_text"]\n\n\n',
    )
    print("SECOND_CATEGORY_SEMANTIC_EVIDENCE_APPLIED")


def diagnose_live() -> None:
    from scripts.public_category_rules import classify_public_category

    targets = {
        "SPECIAL ANNIVERSARY SHOW PLACEBO 30 AÑOS",
        "PREVIA ANIVERSARIO",
        "FIESTA ANIVERSARIO POSEIDON",
        "LOS CUATRO CUARTOS 64 AÑOS DE NEOFOLCLOR, LA TRADICIÓN NOS UNE, CHILE NOS INSPIRA",
        "FERNANDO UBIERGO: 50 AÑOS NO ES NADA EN VALPARAÍSO",
    }
    payload = json.loads(Path("agenda_web.json").read_text(encoding="utf-8"))
    for event in payload.get("events") or []:
        if event.get("source_id") != "portaltickets_valparaiso" or event.get("title") not in targets:
            continue
        result = classify_public_category(event)
        print("CATEGORY_DIAG", json.dumps({
            "title": event.get("title"),
            "venue": (event.get("location") or {}).get("venue"),
            "category": result.get("category"),
            "candidates": result.get("candidates"),
            "source_category": result.get("source_category"),
            "description": event.get("description"),
            "semantic_text": (event.get("semantics") or {}).get("category_evidence_text"),
            "tags": event.get("tags"),
        }, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose-live", action="store_true")
    args = parser.parse_args()
    if args.diagnose_live:
        diagnose_live()
    else:
        apply()


if __name__ == "__main__":
    main()
