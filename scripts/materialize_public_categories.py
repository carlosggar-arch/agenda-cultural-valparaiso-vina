from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.public_category_rules import classify_public_category
DEFAULT_DATASETS = (ROOT / "agenda_web.json", ROOT / "app/data/gijon/agenda_web.json")


def materialize(path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    events = payload.get("events") or []
    for event in events:
        classification = classify_public_category(event)
        category = dict(classification["category"])
        before = (event.get("primary_category"), event.get("categories"))
        event["primary_category"] = category
        event["categories"] = [category]
        semantics = event.get("semantics")
        if isinstance(semantics, dict) and "canonical_category" in semantics:
            semantics["canonical_category"] = category
        after = (event.get("primary_category"), event.get("categories"))
        if before != after:
            changed += 1
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(events), changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the shared semantic public category into city datasets.")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.paths or list(DEFAULT_DATASETS)
    for raw in paths:
        path = raw if raw.is_absolute() else ROOT / raw
        total, changed = materialize(path)
        print(f"PUBLIC_CATEGORIES_MATERIALIZED path={path.relative_to(ROOT)} total={total} changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
