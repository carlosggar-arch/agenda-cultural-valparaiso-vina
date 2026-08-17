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


def migrate_favorites_core_robust() -> None:
    path = migration.ASSETS / "favorites-core.mjs"
    text = path.read_text(encoding="utf-8")
    text, count = re.subn(
        r'^export const FAVORITES_STORAGE_KEY = "agenda-cultural-favorites-v1";\nexport const FAVORITES_CHANGED_EVENT = "agenda-cultural-favorites-changed";\n\nconst SUPPORTED_CITIES = new Set\(\["valparaiso", "gijon"\]\);',
        'import { isSafeCityId, normalizeCityId } from "./city-registry.mjs?v=20260817-city-registry";\n\nexport const FAVORITES_STORAGE_KEY = "agenda-cultural-favorites-v1";\nexport const FAVORITES_CHANGED_EVENT = "agenda-cultural-favorites-changed";',
        text,
        count=1,
        flags=re.M,
    )
    if count != 1:
        raise SystemExit(f"Could not replace favorites city allowlist: {count}")
    replacements = [
        (
            r'const normalizedCity = text\(city\)\.toLocaleLowerCase\("es"\);\n  const normalizedId = text\(id\);\n  if \(!SUPPORTED_CITIES\.has\(normalizedCity\) \|\| !normalizedId\) return null;',
            'const normalizedCity = normalizeCityId(city);\n  const normalizedId = text(id);\n  if (!isSafeCityId(normalizedCity) || !normalizedId) return null;',
        ),
        (r'const city = text\(value\.city\)\.toLocaleLowerCase\("es"\);', 'const city = normalizeCityId(value.city);'),
        (r'const normalizedCity = text\(city\)\.toLocaleLowerCase\("es"\);', 'const normalizedCity = normalizeCityId(city);'),
    ]
    for pattern, replacement in replacements:
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise SystemExit(f"Could not migrate favorites city normalization: {pattern}")
    path.write_text(text, encoding="utf-8")


migration.regex_once = regex_once_multiline
migration.migrate_favorites_core = migrate_favorites_core_robust
migration.main()
