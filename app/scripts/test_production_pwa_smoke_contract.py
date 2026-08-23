from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/production-pwa-smoke.yml").read_text(encoding="utf-8")
REQUIRED = (ROOT / ".github/workflows/required-release-guard.yml").read_text(encoding="utf-8")
TOPOLOGY = json.loads((ROOT / "tests/contract-topology.json").read_text(encoding="utf-8"))
SMOKE = (ROOT / "app/scripts/production_pwa_smoke.py").read_text(encoding="utf-8")
BROWSER_SMOKE = (ROOT / "app/scripts/production_browser_selenium_smoke.py").read_text(encoding="utf-8")
WARM_SMOKE = (ROOT / "app/scripts/production_warm_start_smoke.py").read_text(encoding="utf-8")
PWA_PARITY = (ROOT / "app/scripts/test_web_pwa_visibility_parity.py").read_text(encoding="utf-8")
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
    assert "pull_request:" not in triggers, "Production smoke must be post-merge/manual only after D4"
    assert "push:" in triggers and "branches: [main]" in triggers
    assert "workflow_dispatch:" in triggers, "Production smoke must remain manually rerunnable against main"
    assert '      - "app/**"' not in triggers, "Production smoke must not wake for every app file"
    for marker in (
        '      - "app/*.js"',
        '      - "app/*.mjs"',
        '      - "app/*.css"',
        '      - "app/*.html"',
        '      - "app/*.webmanifest"',
        '      - "agenda_web.json"',
        '      - "app/data/gijon/agenda_web.json"',
        '      - "fuentes_publicas.json"',
        '      - "app/data/source-registry.json"',
        '      - "app/scripts/production_pwa_smoke.py"',
        '      - "app/scripts/production_browser_selenium_smoke.py"',
        '      - "app/scripts/production_warm_start_smoke.py"',
        '      - "app/scripts/test_web_pwa_visibility_parity.py"',
        '      - ".github/workflows/production-pwa-smoke.yml"',
    ):
        assert marker in triggers, f"Production smoke trigger missing: {marker}"

    assert "pr-contract:" not in WORKFLOW, "Local PR smoke must be owned by Required release guard after D4"
    assert "production-smoke:" in WORKFLOW
    production = block("  production-smoke:\n")

    assert "Install browser timing dependency" in production
    assert "selenium==4.35.0" in production
    assert "Require release bump for runtime pushes" in production
    assert "if: github.event_name == 'push'" in production
    assert "Align smoke candidate with latest public main" in production
    assert "git reset --hard origin/main" in production
    assert "app/release-version.js" in production
    assert "js|mjs|css|html|webmanifest" in production
    assert "python app/scripts/production_pwa_smoke.py local" in production
    assert "python app/scripts/production_pwa_smoke.py http" in production
    assert "python app/scripts/production_browser_selenium_smoke.py" in production
    assert "python app/scripts/production_pwa_smoke.py browser" not in production
    assert "python app/scripts/production_warm_start_smoke.py" in production
    assert "python app/scripts/test_web_pwa_visibility_parity.py --production" in production
    assert "Warm-reopen Valpo mobile on GitHub Pages and Cloudflare" in production
    assert "Require exact live WEB versus cached PWA event IDs" in production
    assert "timeout-minutes: 25" in production
    assert "verify byte parity" in production
    assert "GitHub Pages and Cloudflare" in production

    contracts = {entry["id"]: entry for entry in TOPOLOGY["contracts"]}
    required_profile = TOPOLOGY["runner_profiles"]["required-release"]
    local_smoke = contracts["release.local-pwa-smoke"]
    assert local_smoke["owner"] == "app/scripts/production_pwa_smoke.py"
    assert local_smoke["runner_args"] == ["local"]
    assert local_smoke["workflow"] == ".github/workflows/required-release-guard.yml"
    assert "release.local-pwa-smoke" in required_profile
    assert "release.production-smoke-contract" in required_profile
    assert "architecture.public-presentation" in required_profile
    assert "python app/scripts/run_contracts.py --profile required-release" in REQUIRED
    assert "production_pwa_smoke.py http" not in REQUIRED
    assert "production_pwa_smoke.py browser" not in REQUIRED
    assert "production_warm_start_smoke.py" in REQUIRED, "Required gate must at least compile the warm-smoke owner"
    assert "test_web_pwa_visibility_parity.py --local" in REQUIRED, "Required gate must prove local live/cached exact-ID parity"
    assert "node --check app/sources-toggle.js" in REQUIRED

    for stale in ("20260817-brandicon1", "20260817-topcontrols4", "hero-v4-mobile-direct-actions"):
        assert stale not in SMOKE, f"Hard-coded presentation revision returned to production smoke: {stale}"

    assert '"github-pages": "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/app/"' in SMOKE
    assert '"cloudflare": "https://vivamos.pages.dev/app/"' in SMOKE
    assert "CRITICAL_ASSETS" in SMOKE
    assert "hashlib.sha256" in SMOKE
    assert "attempts: int = 36" in SMOKE
    assert "interval: int = 10" in SMOKE
    assert "data-sources-toggle" in SMOKE
    assert 'data-filter-value="manana"' in SMOKE

    for marker in (
        '("valparaiso", "Valparaíso / Viña del Mar", 390, 844)',
        '("gijon", "Gijón / Xixón", 1280, 900)',
        "webdriver.Chrome",
        "WebDriverWait",
        'options.page_load_strategy = "eager"',
        "dataset.vivamosReady",
        "document.querySelectorAll('.event-card').length > 0",
        "[data-sources-toggle], [data-sources-fallback]",
        "PRODUCTION_COLD_LOAD_OK",
        "PRODUCTION_CITY_ROUNDTRIP_OK",
        "transport=selenium",
        "after retry",
    ):
        assert marker in BROWSER_SMOKE, f"Selenium cold-browser smoke contract missing: {marker}"
    assert "--dump-dom" not in BROWSER_SMOKE, "Cold-browser production smoke must not regress to direct Chrome dump-dom"

    for marker in (
        'MOBILE_CITY = "valparaiso"',
        "MOBILE_WIDTH = 390",
        "MOBILE_HEIGHT = 844",
        'CACHE_MARKER_KEY = "vivamos-processed-pipeline-marker-valparaiso"',
        "READY_TIMEOUT_SECONDS = 20",
        "CACHE_WRITE_TIMEOUT_SECONDS = 15",
        "MAX_WARM_RATIO = 1.75",
        "MAX_WARM_EXTRA_SECONDS = 4.0",
        "webdriver.Chrome",
        "WebDriverWait",
        'options.page_load_strategy = "eager"',
        "dataset.vivamosReady",
        "document.querySelectorAll('.event-card').length > 0",
        "wait_for_processed_cache",
        "time.monotonic()",
        "PRODUCTION_WARM_REOPEN_OK",
        "processed_cache=ready",
        "cold_seconds",
        "warm_seconds",
    ):
        assert marker in WARM_SMOKE, f"Warm production smoke contract missing: {marker}"
    assert "profile_dom" not in WARM_SMOKE, "Warm timing must measure core-ready, not dump-dom completion"

    for marker in (
        'STATES = ("hoy", "7-dias", "todos")',
        'data-combined-when',
        "WEB_PWA_VISIBILITY_PARITY_OK",
        "WEB_PWA_VISIBILITY_MISMATCH",
        "Network.emulateNetworkConditions",
        "wait_service_worker",
        '"github-pages"',
        '"cloudflare"',
    ):
        assert marker in PWA_PARITY, f"Exact WEB/PWA parity smoke missing: {marker}"

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
