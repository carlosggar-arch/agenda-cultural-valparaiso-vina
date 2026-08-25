from __future__ import annotations

import json
from pathlib import Path

path = Path('shared/public-category-taxonomy.json')
payload = json.loads(path.read_text(encoding='utf-8'))
changed = 0
for rule in payload['rules'].get('source_title_evidence', []):
    if rule.get('source_id') != 'portaltickets_valparaiso':
        continue
    pattern = str(rule.get('pattern') or '')
    fixed = pattern.replace('\\\\', '\\')
    if fixed != pattern:
        rule['pattern'] = fixed
        changed += 1
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'SPARSE_PATTERN_ENCODING_FIXED count={changed}')
