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


def migrate_gijon_stability_contract() -> None:
    path = migration.APP / "scripts" / "test_gijon_v1_stable.py"
    text = path.read_text(encoding="utf-8")
    old = '''    checks = {\n        "manual_city_choice": (\n            'data-city-option="valparaiso"' in index\n            and 'data-city-option="gijon"' in index\n        ),\n        "location_choice": (\n            "data-use-location" in index\n            and "navigator.geolocation.getCurrentPosition" in app_js\n            and "suggestCityFromCoordinates" in app_js\n        ),\n        "city_persistence": (\n            'const STORAGE_KEY = "agenda-cultural-city"' in app_js\n            and "localStorage.setItem(STORAGE_KEY" in app_js\n        ),\n        "first_run_city_flow": (\n            "city-first-run.js" in index\n            and "agenda-cultural-city" in first_run\n        ),\n        "favorites_wired": (\n            'import "./favorites.js";' in pwa_js\n            and "FAVORITES_STORAGE_KEY" in favorites\n            and "data-favorites-access" in favorites\n            and "data-my-plans-page" in mis_planes\n        ),\n        "plan_ahead_wired": (\n            'import "./plan-ahead.js";' in pwa_js\n            and "selectPlanAhead" in plan_ahead\n        ),\n        "mobile_experience_wired": 'import "./mobile-experience.js";' in pwa_js,\n        "single_shell_two_datasets": (\n            'dataset: "../agenda_web.json"' in app_js\n            and 'dataset: "./data/gijon/agenda_web.json"' in app_js\n        ),\n    }'''
    new = '''    registry = json.loads((APP / "cities.json").read_text(encoding="utf-8"))\n    registry_ids = {str(city.get("id") or "") for city in registry.get("cities", [])}\n    checks = {\n        "manual_city_choice": (\n            "data-city-options" in index\n            and {"valparaiso", "gijon"}.issubset(registry_ids)\n            and "renderCityOptions" in app_js\n        ),\n        "location_choice": (\n            "data-use-location" in index\n            and "navigator.geolocation.getCurrentPosition" in app_js\n            and "suggestCityFromCoordinates" in app_js\n        ),\n        "city_persistence": (\n            "CITY_STORAGE_KEY" in app_js\n            and "localStorage.setItem(STORAGE_KEY" in app_js\n        ),\n        "first_run_city_flow": (\n            "city-first-run.js" in index\n            and "CITY_STORAGE_KEY" in first_run\n            and "loadCityRegistry" in first_run\n        ),\n        "favorites_wired": (\n            'import "./favorites.js";' in pwa_js\n            and "FAVORITES_STORAGE_KEY" in favorites\n            and "data-favorites-access" in favorites\n            and "data-my-plans-page" in mis_planes\n        ),\n        "plan_ahead_wired": (\n            'import "./plan-ahead.js";' in pwa_js\n            and "selectPlanAhead" in plan_ahead\n        ),\n        "mobile_experience_wired": 'import "./mobile-experience.js";' in pwa_js,\n        "single_shell_two_datasets": (\n            "const CITIES = CITY_REGISTRY.byId" in app_js\n            and "fetch(city.dataset" in app_js\n            and {"valparaiso", "gijon"}.issubset(registry_ids)\n        ),\n    }'''
    if old not in text:
        raise SystemExit("Could not locate legacy Gijon runtime contract")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


migration.regex_once = regex_once_multiline
migration.migrate_favorites_core = migrate_favorites_core_robust
# Workflow updates are committed separately with a token that has workflow permission.
migration.migrate_workflow = lambda: None
migration.main()
migrate_gijon_stability_contract()
