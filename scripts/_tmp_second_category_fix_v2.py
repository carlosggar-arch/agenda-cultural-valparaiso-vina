from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found: {path}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Shared classifier: event location/source metadata is noise in the title as well
# as the description. Source-specific exact-title evidence remains untouched.
replace_once(
    "scripts/public_category_rules.py",
    '    _add_rule_evidence(\n        scores, evidence, fold(event.get("title")), TITLE_EVIDENCE_RULES, "title"\n    )\n',
    '    _add_rule_evidence(\n        scores, evidence, _strip_semantic_noise(str(event.get("title") or ""), event), TITLE_EVIDENCE_RULES, "title"\n    )\n',
)
replace_once(
    "app/public-category-rules.mjs",
    '  addRuleEvidence(\n    scores,\n    evidence,\n    foldPublicCategoryText(event?.title),\n    TITLE_EVIDENCE_RULES,\n    "title",\n  );\n',
    '  addRuleEvidence(\n    scores,\n    evidence,\n    stripSemanticNoise(event?.title, event),\n    TITLE_EVIDENCE_RULES,\n    "title",\n  );\n',
)

# PortalTickets has no trustworthy thematic source category. Keep any title-only
# preliminary category for immediate parser diagnostics, but explicitly preserve
# the actual source category as neutral. This prevents a derived result from
# feeding back as source authority when the full detail description is classified.
replace_once(
    "app/scripts/refresh_portaltickets_editorial.py",
    '        "primary_category": {"id": category_id, "label": category_label},\n        "categories": [{"id": category_id, "label": category_label}],\n',
    '        "primary_category": {"id": category_id, "label": category_label},\n        "categories": [{"id": category_id, "label": category_label}],\n        "semantics": {"source_category": {"id": "cultura", "label": "Cultura"}},\n',
)
replace_once(
    "app/scripts/refresh_portaltickets_editorial.py",
    '        "tags": [category_label, "PortalTickets"], "audience": None, "registration_requirements": None,\n',
    '        "tags": ["PortalTickets"], "audience": None, "registration_requirements": None,\n',
)
replace_once(
    "app/scripts/refresh_portaltickets_editorial.py",
    '        tags = [tag for tag in (event.get("tags") or []) if norm(tag) not in {"cultura", "musica", "teatro", "cine", "otros panoramas"}]\n        event["tags"] = [category["label"], *tags]\n',
    '        tags = [tag for tag in (event.get("tags") or []) if norm(tag) not in {"cultura", "musica", "teatro", "teatro y danza", "cine", "otros panoramas"}]\n        if not any(norm(tag) == "portaltickets" for tag in tags):\n            tags.append("PortalTickets")\n        event["tags"] = tags\n',
)

# Cross-language regression: a venue phrase embedded in the source title cannot
# turn a concert into theatre when that exact phrase is also the event location.
replace_once(
    "app/scripts/test_public_category_regressions.py",
    '    assert_case(\n        "flamenco typo and Gipsy Kings remain music",\n        event("Mario Reyes Leyenda Gipsy", "cultura", description="Noche con Mario Reyes leyenda Gipsy Kings, tablao y baile flameno."),\n        "musica",\n    )\n',
    '    assert_case(\n        "flamenco typo and Gipsy Kings remain music",\n        event("Mario Reyes Leyenda Gipsy", "cultura", description="Noche con Mario Reyes leyenda Gipsy Kings, tablao y baile flameno."),\n        "musica",\n    )\n    assert_case(\n        "venue phrase in title is semantic noise",\n        event(\n            "ESTOY BIEN EN TEATRO MAURI SCD VALPARAISO - GIRA NACIONAL",\n            "cultura",\n            description="Banda de punk rock presenta su nuevo disco y sus canciones en gira nacional.",\n            venue="Teatro Mauri SCD, Valparaíso",\n            city="Valparaíso",\n        ),\n        "musica",\n    )\n',
)
replace_once(
    "app/public-category-regressions.test.mjs",
    'expectCategory("flamenco typo and Gipsy Kings", event(\n  "Mario Reyes Leyenda Gipsy",\n  "cultura",\n  { description: "Noche con Mario Reyes leyenda Gipsy Kings, tablao y baile flameno." },\n), "musica");\n',
    'expectCategory("flamenco typo and Gipsy Kings", event(\n  "Mario Reyes Leyenda Gipsy",\n  "cultura",\n  { description: "Noche con Mario Reyes leyenda Gipsy Kings, tablao y baile flameno." },\n), "musica");\nexpectCategory("venue phrase in title is semantic noise", event(\n  "ESTOY BIEN EN TEATRO MAURI SCD VALPARAISO - GIRA NACIONAL",\n  "cultura",\n  { description: "Banda de punk rock presenta su nuevo disco y sus canciones en gira nacional.", venue: "Teatro Mauri SCD, Valparaíso", city: "Valparaíso" },\n), "musica");\n',
)

# Source regression: title-only preliminary output must not become source evidence.
portal_test = Path("app/scripts/test_portaltickets_editorial.py")
text = portal_test.read_text(encoding="utf-8")
anchor = '''def test_shared_source_classifier_does_not_treat_bare_musical_as_music() -> None:\n    category_id, _ = __import__("refresh_portaltickets_editorial").category_for("High School Musical Sing Along (2006)")\n    assert category_id == "cine"\n'''
addition = '''def test_preliminary_category_is_not_reused_as_source_authority() -> None:\n    year = future_year()\n    listing = f\'\'\'<div><h3>QUILAPAYUN EN TEATRO MAURI SCD VALPARAÍSO</h3>\n    <p>Sábado 10 de octubre {year}, 20:00</p><p>Teatro Mauri SCD, Valparaíso</p>\n    <a href="/evento/quilapayun">TICKETS AQUÍ</a></div>\'\'\'\n    events, _ = parse_markup(listing)\n    event = events[0]\n    assert event["semantics"]["source_category"] == {"id": "cultura", "label": "Cultura"}\n    assert event["tags"] == ["PortalTickets"]\n    detail = parse_detail_markup(\'\'\'<h4>Descripción</h4>\n    <p>Quilapayún vuelve con un concierto que recorre su trayectoria y sus canciones más emblemáticas.</p>\n    <p>La agrupación celebra seis décadas de música chilena y folclore latinoamericano.</p>\n    <h4>POLÍTICAS DE REEMBOLSO</h4>\'\'\')\n    enriched = apply_detail(event, detail, verified_at="2026-08-25T10:00:00-04:00")\n    assert enriched["primary_category"] == {"id": "musica", "label": "Música"}\n    assert enriched["tags"] == ["PortalTickets"]\n\n\n'''
if anchor not in text:
    raise SystemExit("PortalTickets source-authority test anchor not found")
text = text.replace(anchor, anchor + addition, 1)
main_anchor = "    test_shared_source_classifier_does_not_treat_bare_musical_as_music()\n"
if main_anchor not in text:
    raise SystemExit("PortalTickets main test anchor not found")
text = text.replace(main_anchor, main_anchor + "    test_preliminary_category_is_not_reused_as_source_authority()\n", 1)
portal_test.write_text(text, encoding="utf-8")

print("SECOND_CATEGORY_AUTHORITY_V2_APPLIED")
