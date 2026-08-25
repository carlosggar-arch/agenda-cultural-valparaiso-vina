from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "shared/public-category-taxonomy.json"
data = json.loads(path.read_text(encoding="utf-8"))

for rule in data["rules"]["title_evidence"]:
    if rule.get("category") != "teatro":
        continue
    pattern = rule.get("pattern", "")
    if "comedia musical|teatro musical|obra musical|espectaculo musical" in pattern:
        rule["pattern"] = r"\b(?:comedia musical|teatro musical|obra musical|espectaculo musical|(?:el|la|un|una) musical)\b"
        break
else:
    raise SystemExit("THEATRE_MUSICAL_RULE_NOT_FOUND")

path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("CONTEXTUAL_MUSICAL_RULE_REFINED")
