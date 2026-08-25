from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()


def main() -> None:
    path = ROOT / "shared/public-category-taxonomy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    rules = payload["rules"]

    # The existing rule also contains `poesia`. Raising that whole rule made
    # Matriarcas drift back to Literatura. Keep that broad mixed rule at its
    # established weight and add a narrowly scoped event-format rule instead.
    restored = False
    for rule in rules.get("title_evidence", []):
        pattern = str(rule.get("pattern") or "")
        if (
            rule.get("category") == "literatura"
            and "presentacion" in pattern
            and "libro" in pattern
            and "poesia" in pattern
        ):
            rule["weight"] = 140
            restored = True
            break
    if not restored:
        raise SystemExit("COMBINED_LITERATURE_TITLE_RULE_NOT_FOUND")

    explicit_pattern = r"\b(?:presentacion (?:del? )?libro|lanzamiento (?:del? )?libro)\b"
    if not any(
        rule.get("category") == "literatura" and rule.get("pattern") == explicit_pattern
        for rule in rules.get("title_evidence", [])
    ):
        rules.setdefault("title_evidence", []).insert(0, {
            "category": "literatura",
            "pattern": explicit_pattern,
            "weight": 260,
        })

    payload["schema_version"] = "2.6.0"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SEMANTIC_CONTENT_INTEGRITY_V2_APPLIED")


if __name__ == "__main__":
    main()
