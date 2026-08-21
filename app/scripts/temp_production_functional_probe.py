from __future__ import annotations

import html
import re

from production_pwa_smoke import ORIGINS, chrome_binary, cold_dom, release_number

EXPECTED_RELEASE = release_number()
CASES = (
    ("valparaiso", "Valparaíso / Viña del Mar", 390, 844),
    ("gijon", "Gijón / Xixón", 1280, 900),
)

chrome = chrome_binary()
errors: list[str] = []

for origin, base in ORIGINS.items():
    for city, label, width, height in CASES:
        try:
            dom = cold_dom(chrome, origin, base, city, width, height)
        except Exception as exc:
            errors.append(f"{origin}/{city}: Chrome failed: {exc}")
            print(f"FUNCTIONAL_PROBE_FAIL origin={origin} city={city} error={exc!r}")
            continue

        version_node = re.search(r"data-app-version[^>]*>(.*?)</", dom, flags=re.S)
        visible_version = html.unescape(re.sub(r"<[^>]+>", "", version_node.group(1))).strip() if version_node else "<missing>"
        cards = dom.count('class="event-card')
        source_controls = dom.count("data-sources-toggle") + dom.count("data-sources-fallback")
        city_applied = f'data-city="{city}"' in dom
        city_label = label in dom
        ready = 'data-vivamos-ready="true"' in dom
        safe_mode = 'data-vivamos-safe-mode="active"' in dom
        agenda_hidden = bool(re.search(r"<section[^>]*data-agenda[^>]*\shidden(?:=|\s|>)", dom))

        print(
            "FUNCTIONAL_PROBE "
            f"origin={origin} city={city} version={visible_version!r} "
            f"cards={cards} sources={source_controls} city_applied={city_applied} "
            f"city_label={city_label} ready={ready} safe_mode={safe_mode} agenda_hidden={agenda_hidden}"
        )

        if visible_version != f"PWA v{EXPECTED_RELEASE}":
            errors.append(f"{origin}/{city}: visible version {visible_version!r}, expected PWA v{EXPECTED_RELEASE}")
        if not city_applied:
            errors.append(f"{origin}/{city}: city not applied")
        if not city_label:
            errors.append(f"{origin}/{city}: city label missing")
        if cards <= 0:
            errors.append(f"{origin}/{city}: no event cards")
        if source_controls <= 0:
            errors.append(f"{origin}/{city}: source control missing")
        if agenda_hidden:
            errors.append(f"{origin}/{city}: agenda still hidden")

if errors:
    print("FUNCTIONAL_PROBE_ERRORS")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print(f"FUNCTIONAL_PROBE_OK release=v{EXPECTED_RELEASE} cases={len(ORIGINS) * len(CASES)}")
