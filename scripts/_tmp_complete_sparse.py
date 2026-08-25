from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()
TAX = ROOT / 'shared/public-category-taxonomy.json'
PY_REG = ROOT / 'app/scripts/test_public_category_regressions.py'
JS_REG = ROOT / 'app/public-category-regressions.test.mjs'

payload = json.loads(TAX.read_text(encoding='utf-8'))
rules = payload['rules']
extra = [
    ('musica', r'\besstelar bday\b', 'verified_sparse_music_event_portaltickets'),
    ('musica', r'\bspecial anniversary show placebo 30 anos\b', 'verified_sparse_music_event_portaltickets'),
    ('musica', r'\bprevia aniversario\b', 'verified_sparse_music_event_portaltickets'),
    ('musica', r'\bla fiesta de ritoque fm\b', 'verified_sparse_music_event_portaltickets'),
    ('ferias-vida-local', r'\boshikatsu party oshifonda\b', 'verified_sparse_fandom_party_portaltickets'),
]
existing = {(r.get('source_id'), r.get('category'), r.get('pattern')) for r in rules.get('source_title_evidence', [])}
for category, pattern, reason in extra:
    key = ('portaltickets_valparaiso', category, pattern)
    if key not in existing:
        rules.setdefault('source_title_evidence', []).append({
            'category': category,
            'pattern': pattern,
            'reason': reason,
            'source_id': 'portaltickets_valparaiso',
            'weight': 120,
        })
TAX.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

py = PY_REG.read_text(encoding='utf-8')
marker = '    audit_current_theatre_conflicts()\n'
insert = '''    for sparse_title in (\n        "Esstelar Bday",\n        "Special Anniversary Show Placebo 30 Años",\n        "Previa Aniversario",\n        "La Fiesta de Ritoque Fm",\n    ):\n        value = event(sparse_title, "cultura", city="Valparaíso")\n        value["source_id"] = "portaltickets_valparaiso"\n        assert_case(f"verified sparse PortalTickets music event: {sparse_title}", value, "musica")\n    oshikatsu = event("Oshikatsu Party Oshifonda", "cultura", city="Valparaíso")\n    oshikatsu["source_id"] = "portaltickets_valparaiso"\n    assert_case("verified sparse PortalTickets fandom party", oshikatsu, "ferias-vida-local")\n    audit_current_theatre_conflicts()\n'''
if marker not in py or py.count(marker) != 1:
    raise SystemExit('PY_REG_MARKER_INVALID')
PY_REG.write_text(py.replace(marker, insert, 1), encoding='utf-8')

js = JS_REG.read_text(encoding='utf-8')
marker_js = 'console.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");\n'
insert_js = '''for (const sparseTitle of [\n  "Esstelar Bday",\n  "Special Anniversary Show Placebo 30 Años",\n  "Previa Aniversario",\n  "La Fiesta de Ritoque Fm",\n]) {\n  expectCategory(`verified sparse PortalTickets music event: ${sparseTitle}`, {\n    ...event(sparseTitle, "cultura", { city: "Valparaíso" }),\n    source_id: "portaltickets_valparaiso",\n  }, "musica");\n}\nexpectCategory("verified sparse PortalTickets fandom party", {\n  ...event("Oshikatsu Party Oshifonda", "cultura", { city: "Valparaíso" }),\n  source_id: "portaltickets_valparaiso",\n}, "ferias-vida-local");\nconsole.log("PUBLIC_CATEGORY_JS_REGRESSIONS_OK");\n'''
if marker_js not in js or js.count(marker_js) != 1:
    raise SystemExit('JS_REG_MARKER_INVALID')
JS_REG.write_text(js.replace(marker_js, insert_js, 1), encoding='utf-8')
print('COMPLETE_SPARSE_PORTALTICKETS_RULES_APPLIED')
