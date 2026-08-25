from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def replace_exact(path: str, old_lines: list[str], new_lines: list[str]) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    old = "\n".join(old_lines) + "\n"
    new = "\n".join(new_lines) + "\n"
    if old not in text:
        raise SystemExit(f"anchor not found: {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply() -> None:
    replace_exact(
        "scripts/public_category_rules.py",
        [
            "def _scalar_noise_values(value: Any) -> list[str]:",
            "    if isinstance(value, str):",
            "        return [value]",
            "    if isinstance(value, dict):",
            "        return [",
            '            str(value.get(key) or "")',
            '            for key in ("name", "label", "title", "address", "city", "venue")',
            "            if value.get(key)",
            "        ]",
            "    return []",
        ],
        [
            "def _scalar_noise_values(value: Any) -> list[str]:",
            "    if isinstance(value, str):",
            "        return [value]",
            "    if not isinstance(value, dict):",
            "        return []",
            "    values = [",
            '        str(value.get(key) or "")',
            '        for key in ("name", "label", "title", "address", "city", "venue")',
            "        if value.get(key)",
            "    ]",
            '    venue = fold(value.get("venue"))',
            '    city = fold(value.get("city"))',
            '    if venue and city and venue.endswith(f" {city}"):',
            '        short_venue = venue[: -(len(city) + 1)].strip()',
            "        if len(short_venue) >= 4:",
            "            values.append(short_venue)",
            "    return values",
        ],
    )

    replace_exact(
        "app/public-category-rules.mjs",
        [
            "function scalarNoiseValues(value) {",
            '  if (typeof value === "string") return [value];',
            '  if (!value || typeof value !== "object" || Array.isArray(value)) return [];',
            '  return ["name", "label", "title", "address", "city", "venue"]',
            "    .map((key) => value[key])",
            "    .filter(Boolean)",
            "    .map(String);",
            "}",
        ],
        [
            "function scalarNoiseValues(value) {",
            '  if (typeof value === "string") return [value];',
            '  if (!value || typeof value !== "object" || Array.isArray(value)) return [];',
            '  const values = ["name", "label", "title", "address", "city", "venue"]',
            "    .map((key) => value[key])",
            "    .filter(Boolean)",
            "    .map(String);",
            "  const venue = foldPublicCategoryText(value.venue);",
            "  const city = foldPublicCategoryText(value.city);",
            "  if (venue && city && venue.endsWith(` ${city}`)) {",
            "    const shortVenue = venue.slice(0, -(city.length + 1)).trim();",
            "    if (shortVenue.length >= 4) values.push(shortVenue);",
            "  }",
            "  return values;",
            "}",
        ],
    )

    taxonomy_path = Path("shared/public-category-taxonomy.json")
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    for family in ("description_evidence", "title_evidence"):
        for rule in taxonomy["rules"][family]:
            if rule["category"] != "musica":
                continue
            if "organetto" in rule["pattern"]:
                rule["pattern"] = rule["pattern"].replace(
                    "organetto)",
                    "organetto|boleros?|vals(?:es)?|vinilos?|gipsy kings?)",
                )
            if "flamenco" in rule["pattern"]:
                rule["pattern"] = rule["pattern"].replace("flamenco", "flamen(?:c)?os?")
    taxonomy_path.write_text(
        json.dumps(taxonomy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    py_test = Path("app/scripts/test_public_category_regressions.py")
    text = py_test.read_text(encoding="utf-8")
    text = text.replace(
        'def event(title, primary, *, tags=None, description="", venue=""):',
        'def event(title, primary, *, tags=None, description="", venue="", city="Gijón"):',
        1,
    ).replace(
        '        "location": {"venue": venue, "city": "Gijón"},',
        '        "location": {"venue": venue, "city": city},',
        1,
    )
    anchor = '    assert_case("venue does not define format", event("Concierto de cuarteto", "cultura", venue="Teatro Jovellanos"), "musica")\n'
    extra = "\n".join(
        [
            "    assert_case(",
            '        "venue alias is semantic noise",',
            "        event(",
            '            "Lucy Briceño",',
            '            "cultura",',
            '            description="Lucy Briceño celebra su trayectoria con un concierto especial en el Teatro Mauri SCD.",',
            '            venue="Teatro Mauri SCD, Valparaíso",',
            '            city="Valparaíso",',
            "        ),",
            '        "musica",',
            "    )",
            "    assert_case(",
            '        "boleros valses and vinyl are music",',
            '        event("Viernes Cebolla", "cultura", description="Una noche de boleros y valses, seguida de baile en vinilo."),',
            '        "musica",',
            "    )",
            "    assert_case(",
            '        "flamenco typo and Gipsy Kings remain music",',
            '        event("Mario Reyes Leyenda Gipsy", "cultura", description="Noche con Mario Reyes leyenda Gipsy Kings, tablao y baile flameno."),',
            '        "musica",',
            "    )",
            "",
        ]
    )
    if anchor not in text:
        raise SystemExit("python regression anchor not found")
    py_test.write_text(text.replace(anchor, anchor + extra, 1), encoding="utf-8")

    js_test = Path("app/public-category-regressions.test.mjs")
    text = js_test.read_text(encoding="utf-8")
    text = text.replace(
        'function event(title, primary, { tags = [], description = "", venue = "" } = {}) {',
        'function event(title, primary, { tags = [], description = "", venue = "", city = "Gijón" } = {}) {',
        1,
    ).replace(
        '    location: { venue, city: "Gijón" },',
        "    location: { venue, city },",
        1,
    )
    anchor = 'expectCategory("venue neutral", event("Concierto de cuarteto", "cultura", { venue: "Teatro Jovellanos" }), "musica");\n'
    extra = "\n".join(
        [
            'expectCategory("venue alias is semantic noise", event(',
            '  "Lucy Briceño",',
            '  "cultura",',
            '  { description: "Lucy Briceño celebra su trayectoria con un concierto especial en el Teatro Mauri SCD.", venue: "Teatro Mauri SCD, Valparaíso", city: "Valparaíso" },',
            '), "musica");',
            'expectCategory("boleros valses and vinyl", event(',
            '  "Viernes Cebolla",',
            '  "cultura",',
            '  { description: "Una noche de boleros y valses, seguida de baile en vinilo." },',
            '), "musica");',
            'expectCategory("flamenco typo and Gipsy Kings", event(',
            '  "Mario Reyes Leyenda Gipsy",',
            '  "cultura",',
            '  { description: "Noche con Mario Reyes leyenda Gipsy Kings, tablao y baile flameno." },',
            '), "musica");',
            "",
        ]
    )
    if anchor not in text:
        raise SystemExit("js regression anchor not found")
    js_test.write_text(text.replace(anchor, anchor + extra, 1), encoding="utf-8")


def fold(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def validate_live() -> None:
    from scripts.public_category_rules import classify_public_category

    events = json.loads(Path("agenda_web.json").read_text(encoding="utf-8"))["events"]
    portal = [event for event in events if event.get("source_id") == "portaltickets_valparaiso"]
    print("PORTALTICKETS_LIVE_COUNT", len(portal))
    if len(portal) < 20:
        raise SystemExit(f"unexpectedly low live PortalTickets count: {len(portal)}")

    expected_music = {
        "LUCY BRICEÑO",
        "LOS CRACK DEL PUERTO",
        "VIERNES CEBOLLA",
        "SPECIAL ANNIVERSARY SHOW PLACEBO 30 AÑOS",
        "PREVIA ANIVERSARIO",
        "FIESTA ANIVERSARIO POSEIDON",
        "AILINASHAKTI",
        "LOS CUATRO CUARTOS 64 AÑOS DE NEOFOLCLOR, LA TRADICIÓN NOS UNE, CHILE NOS INSPIRA",
        "JOSE ALFREDO FUENTES 60 GOLD",
        "ESTOY BIEN EN TEATRO MAURI SCD VALPARAISO - GIRA NACIONAL 2026-2027, SEGUNDO LP",
        "QUILAPAYUN",
        "FERNANDO UBIERGO: 50 AÑOS NO ES NADA EN VALPARAÍSO",
        "TATA BARAHONA & LSD - FOTOGRAFÍAS 15 AÑOS",
        "MARIO REYES LEYENDA GIPSY",
    }
    found = 0
    bad: list[tuple[str, str | None]] = []
    for event in portal:
        title = str(event.get("title") or "")
        category = (event.get("primary_category") or {}).get("id")
        if title in expected_music:
            found += 1
            print("LIVE_TARGET", title, category)
            if category != "musica":
                bad.append((title, category))
    if found < 8:
        raise SystemExit(f"too few live regression targets present: {found}")
    if bad:
        bad_titles = {title for title, _ in bad}
        for event in portal:
            if event.get("title") not in bad_titles:
                continue
            result = classify_public_category(event)
            print(
                "LIVE_BAD_DETAIL",
                json.dumps(
                    {
                        "title": event.get("title"),
                        "venue": (event.get("location") or {}).get("venue"),
                        "source_category": (event.get("semantics") or {}).get("source_category"),
                        "tags": event.get("tags"),
                        "description": event.get("description"),
                        "category_evidence_text": (event.get("semantics") or {}).get("category_evidence_text"),
                        "result": result,
                    },
                    ensure_ascii=False,
                ),
            )
        raise SystemExit("live music targets misclassified: " + repr(bad))

    music_signal = re.compile(
        r"\b(?:concierto|musica|musical|cantautor|cantautora|banda|cancion|rock|punk|metal|jazz|bolero|vals|vinilo|flamen(?:c)?o|gipsy kings)\b"
    )
    explicit_stage = re.compile(
        r"\b(?:obra teatral|obra de teatro|teatro musical|comedia musical|ballet|danza|performance|funcion teatral|monologo|stand up|magia|ilusionismo)\b"
    )
    suspicious = []
    for event in portal:
        if (event.get("primary_category") or {}).get("id") != "teatro":
            continue
        text = fold(" ".join([str(event.get("title") or ""), str(event.get("description") or "")]))
        if music_signal.search(text) and not explicit_stage.search(text):
            suspicious.append((event.get("title"), event.get("description")))
    if suspicious:
        raise SystemExit(
            "PortalTickets music evidence still leaking to teatro: " + repr(suspicious[:20])
        )
    print("PORTALTICKETS_LIVE_CATEGORY_AUTHORITY_OK", f"targets={found}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-live", action="store_true")
    args = parser.parse_args()
    if args.validate_live:
        validate_live()
    else:
        apply()
        print("SECOND_CATEGORY_HARDENING_APPLIED")


if __name__ == "__main__":
    main()
