from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.event_semantics import build_event_semantics

FIXTURES = json.loads(
    (ROOT / "shared" / "event-semantics-fixtures.json").read_text(encoding="utf-8")
)


def main() -> int:
    assert FIXTURES["schema_version"] == "1.0.0"
    for fixture in FIXTURES["cases"]:
        semantics = build_event_semantics(fixture["event"])
        expected = fixture["expected"]
        name = fixture["name"]
        assert semantics["category"]["id"] == expected["category"], name
        assert semantics["primary_domain"] == expected["primary_domain"], name
        assert semantics["secondary_domains"] == expected["secondary_domains"], name
        assert semantics["format"] == expected["format"], name
        assert semantics["audience"] == expected["audience"], name
        assert semantics["lifecycle"] == expected["lifecycle"], name
        assert isinstance(semantics["domain_candidates"], list), name
        assert isinstance(semantics["evidence"], list), name

    source_event = {
        "id": "source-provenance",
        "title": "Concierto de jazz",
        "primary_category": {"id": "otros", "label": "Otros panoramas"},
    }
    first = build_event_semantics(source_event)
    normalized = {
        **source_event,
        "primary_category": first["category"],
        "categories": [first["category"]],
        "semantics": first,
    }
    second = build_event_semantics(normalized)
    assert first["primary_domain"] == "musica"
    assert second["primary_domain"] == "musica"
    assert first["source_category"]["id"] == "otros"
    assert second["source_category"]["id"] == "otros"
    assert second["score"] == first["score"]
    assert second["secondary_domains"] == first["secondary_domains"]

    print("PYTHON_EVENT_SEMANTICS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
