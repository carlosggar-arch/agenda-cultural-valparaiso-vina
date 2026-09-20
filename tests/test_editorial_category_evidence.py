from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.event_semantics import build_event_semantics


def main() -> int:
    fixtures = json.loads(
        (ROOT / "shared" / "editorial-category-evidence-fixtures.json").read_text(encoding="utf-8")
    )
    for fixture in fixtures["cases"]:
        event = copy.deepcopy(fixture["event"])
        original = copy.deepcopy(event)
        first = build_event_semantics(event)
        second = build_event_semantics({
            **event,
            "semantics": first,
            "primary_category": first["category"],
            "categories": [first["category"]],
        })
        assert first["category"]["id"] == fixture["category"], fixture["name"]
        assert second == first, fixture["name"]
        assert event == original, fixture["name"]
        for field in ("category_evidence_text", "producer"):
            if field in event.get("semantics", {}):
                assert first[field] == event["semantics"][field], fixture["name"]
    print(f"PYTHON_EDITORIAL_CATEGORY_EVIDENCE_OK cases={len(fixtures['cases'])}")
    return 0


def test_editorial_category_evidence() -> None:
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
