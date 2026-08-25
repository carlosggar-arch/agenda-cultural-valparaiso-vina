from __future__ import annotations

from pathlib import Path

path = Path('app/scripts/test_production_pwa_smoke_contract.py')
text = path.read_text(encoding='utf-8')

old = 'SOURCES = (ROOT / "app/sources-toggle.js").read_text(encoding="utf-8")\n'
new = old + 'RUNTIME_RELEASE_GUARD = (ROOT / "app/scripts/runtime_release_guard.py").read_text(encoding="utf-8")\n'
if text.count(old) != 1:
    raise SystemExit('RUNTIME_GUARD_CONSTANT_MARKER_INVALID')
text = text.replace(old, new, 1)

old = '        \'      - "app/scripts/production_release_attestation.py"\',\n        \'      - ".github/workflows/publish.yml"\',\n'
new = '        \'      - "app/scripts/production_release_attestation.py"\',\n        \'      - "app/scripts/runtime_release_guard.py"\',\n        \'      - ".github/workflows/publish.yml"\',\n'
if text.count(old) != 1:
    raise SystemExit('RUNTIME_GUARD_TRIGGER_MARKER_INVALID')
text = text.replace(old, new, 1)

old = '''    assert "app/release-version.js" in sync\n    assert "js|mjs|css|html|webmanifest" in sync\n    assert "Validate Cloudflare build snapshot and exact release lineage" in sync\n'''
new = '''    assert "app/release-version.js" in sync\n    assert "python app/scripts/runtime_release_guard.py" in sync\n    assert '--base-ref "$before"' in sync\n    assert '--head-ref "$CANDIDATE_SHA"' in sync\n    # Runtime extension ownership now lives in the dedicated guard rather than\n    # being duplicated inline in the workflow. Keep that delegated contract\n    # explicit so the preflight fails if either side drifts again.\n    for marker in ("js|mjs|css|html|webmanifest", "RELEASE_VERSION", "RUNTIME_PATH", "RELEASE_RUNTIME_GUARD_BLOCKED"):\n        assert marker in RUNTIME_RELEASE_GUARD, f"Runtime release guard contract missing: {marker}"\n    assert "Validate Cloudflare build snapshot and exact release lineage" in sync\n'''
if text.count(old) != 1:
    raise SystemExit('STALE_INLINE_REGEX_ASSERTION_MARKER_INVALID')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
print('RUNTIME_RELEASE_GUARD_CONTRACT_ALIGNED')
