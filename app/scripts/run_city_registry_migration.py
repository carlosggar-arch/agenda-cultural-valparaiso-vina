from __future__ import annotations

import re
from pathlib import Path

import migrate_city_registry_architecture as migration


def regex_once_multiline(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S | re.M)
    if count != 1:
        raise SystemExit(f"Expected exactly one regex match in {path}: found {count}")
    path.write_text(updated, encoding="utf-8")


migration.regex_once = regex_once_multiline
migration.main()
