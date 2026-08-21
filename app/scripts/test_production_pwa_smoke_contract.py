from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/production-pwa-smoke.yml").read_text(encoding="utf-8")
SMOKE = (ROOT / "app/scripts/production_pwa_smoke.py").read_text(encoding="utf-8")
WARM_SMOKE = (ROOT / "app/scripts/production_warm_start_smoke.py").read_text(encoding="utf-8")
APP = (ROOT / "app/app.js").read_text(encoding="utf-8")
PWA = (ROOT / "app/pwa.js").read_text(encoding="utf-8")
SOURCES = (ROOT / "app/sources-toggle.js").read_text(encoding="utf-8")


def block(start_marker: str, end_marker: str | None = None) -> str:
    start = WORKFLOW.index(start_marker)
    if end_marker is None:
        return WORKFLOW[start:]
    end = WORKFLOW.index(end_marker, start)
    return WORKFLOW[start:end]


def main() -> None:
    triggers = WORKFLOW.split("permissions:", 1)[0]
    assert '      - "app/**"' not in triggers, "Production smoke must not wake for every app file"
    for marker in (
        '      - "app/*.js"',
        '      - "app/*.css"',
        '      - "app/*.html"',
        '      - "app/*.webmanifest"',
        '      - "agenda_web.json"',
        '      - "app/data/gijon/agenda_web.json"',
        '      - "fuentes_publicas.json"',
        '      - "app/data/source-registry.json"',
        '      - "app/scripts/production_pwa_smoke.py"',
        '      - "app/scripts/production_warm_start_smoke.py"',
        '      - ".github/workflows/production-pwa-smoke.yml"',
    ):
        assert marker in triggers, f"Production smoke trigger missing: {marker}"

    assert "pr-contract:" in WORKFLOW
    assert "production-smoke:" in WORKFLOW
    pr = block("  pr-contract:\n", "  production-smoke:\n")
    production = block("  production-smoke:\n")

    assert "if: github.event_name == 'pull_request'" in pr
    assert "python app/scripts/production_pwa_smoke.py local" in pr
    assert "python app/scripts/test_production_pwa_smoke_contract.py" in pr
    assert "app/scripts/production_warm_start_smoke.py" in pr
    assert "node --check app/sources-toggle.js" in pr
    assert "production_pwa_smoke.py http" not in pr
    assert "production_pwa_smoke.py browser" not in pr
    assert "production_warm_start_smoke.py" not in pr.split("python -m py_compile", 1)[0]

    assert "if: github.event_name != 'pull_request'" in production
    assert "Require release bump for runtime pushes" in production
    assert "Align smoke candidate with latest public main" in production
    assert "git reset --hard origin/main" in production
    assert "app/release-version.js" in production
    assert "python app/scripts/production_pwa_smoke.py http" in production
    assert "python app/scripts/production_pwa_smoke.py browser" in production
    assert "python app/scripts/production_warm_start_smoke.py" in production
    assert "Warm-reopen Valpo mobile on GitHub Pages and Cloudflare" in production
    assert "timeout-minutes: 18" in production
    assert "verify byte parity" in production
    assert "GitHub Pages and Cloudflare" in production

    # Production assertions must derive current asset revisions from source,
    # rather than fossilising version strings inside the smoke implementation.
    for stale in ("20260817-brandicon1", "20260817-topcontrols4", "hero-v4-mobile-direct-actions"):
        assert stale not in SMOKE, f"Hard-coded presentation revision returned to production smoke: {stale}"

    assert '"github-pages": "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/app/"' in SMOKE
    assert '"cloudflare": "https://vivamos.pages.dev/app/"' in SMOKE
    assert "CRITICAL_ASSETS" in SMOKE
    assert "hashlib.sha256" in SMOKE
    assert "attempts: int = 36" in SMOKE
    assert "interval: int = 10" in SMOKE
    assert '("valparaiso", "Valparaíso / Viña del Mar", 390, 844)' in SMOKE
    assert '("gijon", "Gijón / Xixón", 1280, 900)' in SMOKE
    assert "data-sources-toggle" in SMOKE
    assert 'data-filter-value="manana"' in SMOKE
    assert "--disable-background-networking" in SMOKE
    assert "after retry" in SMOKE

    for marker in (
        'MOBILE_CITY = "valparaiso"',
        "MOBILE_WIDTH = 390",
        "MOBILE_HEIGHT = 844",
        "MAX_WARM_RATIO = 1.75",
        "MAX_WARM_EXTRA_SECONDS = 4.0",
        "time.monotonic()",
        "profile_dom",
        "PRODUCTION_WARM_REOPEN_OK",
        "cold_seconds",
        "warm_seconds",
    ):
        assert marker in WARM_SMOKE, f"Warm production smoke contract missing: {marker}"

    # app.js is the only owner of content modules. pwa.js may document them in
    # comments, but it must not list them as OPTIONAL_UI_MODULES entries.
    for marker in ("sources-toggle.js", "community-source.js", "participation-footer.js"):
        assert marker in APP, f"app.js lost content module ownership: {marker}"
    for marker in ('"./sources-toggle.js', '"./community-source.js', '"./participation-footer.js'):
        assert marker not in PWA, f"pwa.js regained duplicate content module ownership: {marker}"

    assert "DIAGNOSTIC_SOURCE_META" not in SOURCES
    for marker in ("canonical_source_id", "eventCountsBySourceId", "runtimeById"):
        assert marker in SOURCES, f"Canonical source mapping missing: {marker}"

    print("PRODUCTION_PWA_SMOKE_CONTRACT_OK")


if __name__ == "__main__":
    main()
