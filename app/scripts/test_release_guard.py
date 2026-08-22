from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
MULTICITY_WORKFLOW = ROOT / ".github/workflows/multi-city-pre-release.yml"
REQUIRED_WORKFLOW = ROOT / ".github/workflows/required-release-guard.yml"
TEMPORAL_WORKFLOW = ROOT / ".github/workflows/temporal-priority-validation.yml"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/production-pwa-smoke.yml"
TOPOLOGY = ROOT / "tests/contract-topology.json"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def release_number() -> int:
    source = text(APP / "release-version.js")
    match = re.search(r"const RELEASE = (\d+);", source)
    assert match, "release-version.js must define a numeric RELEASE"
    return int(match.group(1))


def shell_asset(value: str) -> str:
    return value.split("?", 1)[0]


def shell_contains(manifest: str, value: str) -> bool:
    return f'"{shell_asset(value)}"' in manifest


def check_single_release_source() -> None:
    release = release_number()
    index = text(APP / "index.html")
    pwa = text(APP / "pwa.js")
    sw = text(APP / "service-worker.js")
    shell = text(APP / "service-worker-assets.generated.js")

    head = index.split("</head>", 1)[0]
    assert '<script src="./release-version.js"></script>' in head, "release source must load in <head>"
    assert 'globalThis.__VIVAMOS_RELEASE__' in pwa, "PWA must consume the shared release source"
    assert 'importScripts("./release-version.js", "./service-worker-assets.generated.js")' in sw, (
        "service worker must consume the shared release source and generated shell manifest"
    )
    assert 'const CACHE_VERSION = `v${RELEASE}`' in sw, "cache version must derive from the shared release"
    assert 'service-worker.js?v=${APP_RELEASE}' in pwa, "service-worker registration must derive from the shared release"
    assert shell_contains(shell, "./release-version.js"), "release-version.js must be part of the generated shell cache"

    assert not re.search(r'const APP_VERSION = "PWA v\d+"', pwa), "hard-coded PWA version returned"
    assert not re.search(r'const CACHE_VERSION = "v\d+"', sw), "hard-coded cache version returned"
    assert not re.search(r'service-worker\.js\?v=\d+', pwa), "hard-coded service-worker query version returned"
    assert not re.search(r'data-app-version>PWA v\d+<', index), "HTML footer must not carry a second release number"
    assert release >= 1


def module_url(source: str, stem: str) -> str | None:
    match = re.search(rf'["\'](\./{re.escape(stem)}[^"\']*)["\']', source)
    return match.group(1) if match else None


def check_asset_coherence() -> None:
    index = text(APP / "index.html")
    app_js = text(APP / "app.js")
    pwa = text(APP / "pwa.js")
    schedule_js = text(APP / "schedule-display.js")
    header_js = text(APP / "header-redesign.js")
    shell = text(APP / "service-worker-assets.generated.js")
    head = index.split("</head>", 1)[0]

    header_style = re.search(r'const HEADER_STYLESHEET = "([^"]+)"', header_js)
    assert header_style, "header-redesign.js must declare its canonical stylesheet"
    header_style_href = header_style.group(1)
    assert f'<link rel="stylesheet" href="{header_style_href}">' in head, (
        "header stylesheet in <head> must match header-redesign.js before first paint"
    )
    assert shell_contains(shell, header_style_href), "generated service-worker shell must cache the canonical header stylesheet"

    mobile_style = re.search(
        r'<link rel="stylesheet" href="(\./mobile-experience\.css[^\"]*)" data-mobile-experience-styles>',
        head,
    )
    assert mobile_style, "mobile CSS must be render-blocking in <head>"
    assert shell_contains(shell, mobile_style.group(1)), "generated shell must cache the exact mobile stylesheet"

    header_module = module_url(pwa, "header-redesign.js")
    mobile_module = module_url(pwa, "mobile-experience.js")
    assert header_module, "pwa.js must declare the versioned header module"
    assert mobile_module, "pwa.js must declare the versioned mobile module"
    assert shell_contains(shell, header_module), "generated shell must cache the header module declared by pwa.js"
    assert shell_contains(shell, mobile_module), "generated shell must cache the mobile module declared by pwa.js"

    app_schedule = module_url(app_js, "schedule-display.js")
    pwa_schedule = module_url(pwa, "schedule-display.js")
    assert app_schedule, "app.js must declare the shared schedule display module"
    assert pwa_schedule is None, "pwa.js must not instantiate schedule-display.js"
    assert "?v=" in app_schedule, "schedule display module must be explicitly versioned"
    assert shell_contains(shell, app_schedule), "generated shell must cache the schedule module"

    for stem in ("card-experience.js", "public-presentation-guard.js", "exhibition-hours.js"):
        assert module_url(app_js, stem), f"app.js must own {stem}"
        assert module_url(pwa, stem) is None, f"pwa.js must not instantiate {stem}"

    assert module_url(app_js, "card-image-fallback.js") is None, (
        "legacy card-image-fallback.js must stay removed from app.js"
    )
    assert module_url(pwa, "card-image-fallback.js") is None, (
        "legacy card-image-fallback.js must stay removed from pwa.js"
    )
    assert not shell_contains(shell, "./card-image-fallback.js"), (
        "legacy card-image-fallback.js must stay out of the generated shell"
    )

    formatter = re.search(r'from "(\.\./assets/event-schedule-display\.mjs[^\"]*)"', schedule_js)
    assert formatter, "schedule-display.js must import the shared schedule formatter"
    assert "?v=" in formatter.group(1), "shared schedule formatter must be explicitly versioned"
    assert shell_contains(shell, formatter.group(1)), "generated shell must cache the shared schedule formatter"


def check_manifest_entrypoint() -> None:
    manifest = json.loads(text(APP / "manifest.webmanifest"))
    root_manifest = json.loads(text(ROOT / "manifest.webmanifest"))
    assert manifest.get("id") == "./", "installed app id must remain the clean app root"
    assert manifest.get("start_url") == "./", "installed app must start at the clean app root"
    assert manifest.get("scope") == "./", "installed app scope must remain the app root"
    assert root_manifest.get("id") == "./app/", "root manifest id must target the clean app root"
    assert root_manifest.get("start_url") == "./app/", "root manifest start_url must target the clean app root"
    assert root_manifest.get("scope") == "./app/", "root manifest scope must target the app root"
    assert "?pwa=" not in text(APP / "manifest.webmanifest"), "stale cache-busting query returned to app manifest"
    assert "?pwa=" not in text(ROOT / "manifest.webmanifest"), "stale cache-busting query returned to root manifest"


def check_first_render_contract() -> None:
    index = text(APP / "index.html")
    mobile = text(APP / "mobile-experience.js")
    header_js = text(APP / "header-redesign.js")
    head = index.split("</head>", 1)[0]
    app_module = re.search(r'<script type="module" src="\./app\.js[^"]*"></script>', index)
    assert app_module, "app shell must load app.js as a module"
    before_modules = index[:app_module.start()]

    assert 'data-mobile-experience-styles' in head, "mobile CSS must load before first paint"
    assert 'document.createElement("link")' not in mobile, "mobile CSS must never be injected after first paint"
    assert 'document.head.append(link)' not in mobile, "mobile CSS must never be appended dynamically"
    assert 'links[0].href =' not in header_js, "header CSS href must never be rewritten after first paint"
    assert 'links[0].setAttribute("href"' not in header_js, "header CSS href must never be rewritten after first paint"

    required_initial_markup = (
        'data-header-redesign="hero-v3"',
        'data-header-city-title',
        'data-header-search-toggle',
        'data-header-search-popover',
        'class="header-bottom"',
        'class="header-art"',
    )
    for marker in required_initial_markup:
        assert marker in before_modules, f"first-render header markup missing: {marker}"

    assert 'document.documentElement.dataset.city' in head, "city must be applied before body paint"
    assert 'new URLSearchParams(window.location.search).get("city")' in head, "requested city must win before first paint"
    assert 'data-initial-city-chrome' in before_modules, "initial city chrome must be filled synchronously"


def check_startup_resilience_contract() -> None:
    app_js = text(APP / "app.js")
    core = text(APP / "app-core.js")
    pipeline = text(APP / "data-pipeline.js")
    policy = text(APP / "program-visibility-policy.js")
    watchdog = text(APP / "startup-stability.js")
    lifecycle = text(APP / "render-lifecycle.js")

    assert "await coreReady;" in app_js, "optional app modules must wait for core readiness"
    assert 'loadAgendaDataset' in core and 'vivamos:core-ready' in core, "app-core must own and settle startup"
    assert 'function applyStage' in pipeline and 'status: "skipped"' in pipeline, "data transforms must fail open"
    assert 'publishAgendaRuntimeSnapshot' in pipeline, "normalized pipeline must publish shared runtime state"
    assert 'new MutationObserver' not in policy, "program policy must not observe and mutate its own DOM"
    assert '.fetch =' not in policy, "program policy must not monkey-patch fetch"
    assert 'SAFE_MODE_DELAY_MS = 5000' in watchdog and 'app-safe-mode.js' in watchdog, "startup watchdog must provide safe mode"
    assert 'new MutationObserver' in lifecycle, "one bounded render lifecycle observer must exist"
    assert 'subtree: true' not in lifecycle and 'characterData: true' not in lifecycle, "render lifecycle must not observe descendant churn"


def check_workflow_guard() -> None:
    multicity = text(MULTICITY_WORKFLOW)
    required = text(REQUIRED_WORKFLOW)
    temporal = text(TEMPORAL_WORKFLOW)
    production = text(PRODUCTION_WORKFLOW)
    topology = json.loads(text(TOPOLOGY))
    contracts = {entry["id"]: entry for entry in topology["contracts"]}
    profiles = topology["runner_profiles"]
    scenarios = topology["browser_scenarios"]

    assert topology["schema_version"] == "1.3.0", "D4 final contract topology is not active"
    release_contract = contracts["release.generated-shell"]
    assert release_contract["owner"] == "app/scripts/test_release_guard.py"
    assert release_contract["workflow"] == ".github/workflows/required-release-guard.yml"

    for contract_id in (
        "release.generated-shell",
        "architecture.startup",
        "architecture.public-presentation",
        "release.local-pwa-smoke",
        "release.production-smoke-contract",
    ):
        assert contract_id in profiles["required-release"], f"required-release profile missing {contract_id}"
    assert contracts["release.local-pwa-smoke"]["runner_args"] == ["local"]
    assert profiles["temporal-fast"] == ["semantic.temporal-priority", "semantic.agenda-order"]

    assert "python app/scripts/run_contracts.py --profile required-release" in required, (
        "required release contracts must be invoked through the canonical runner"
    )
    assert "python app/scripts/run_browser_scenarios.py --all" in required, (
        "required release gate must compose every canonical browser scenario"
    )
    assert "python app/scripts/run_contracts.py --profile temporal-fast" in temporal, (
        "temporal PR validation must stay on its fast semantic profile"
    )
    assert "_browser.py" not in temporal, "temporal workflow must not launch browser tests after D4"

    for entry in contracts.values():
        if entry["layer"] == "browser":
            assert entry.get("workflow") == ".github/workflows/required-release-guard.yml", (
                f"browser owner escaped the single required gate: {entry['id']}"
            )
    assert scenarios["startup-city"] == [
        "browser.first-render",
        "browser.startup-resilience",
        "browser.city-switch",
    ]
    assert "browser.runtime-user-flow" in scenarios["filters-detail-media"]
    assert "browser.exhibition-visual-parity" in scenarios["exhibitions"]
    assert scenarios["temporal-order"] == ["browser.temporal-priority"]
    assert topology["temporary_overlaps"] == [], "D4 must leave no temporary overlap"

    for browser_command in (
        "python app/scripts/test_first_render_browser.py",
        "python app/scripts/test_temporal_priority_browser.py",
        "python app/scripts/run_browser_scenarios.py",
    ):
        assert browser_command not in multicity, f"browser execution leaked into multi-city gate: {browser_command}"

    production_triggers = production.split("permissions:", 1)[0]
    assert "pull_request:" not in production_triggers, "production smoke must be post-merge/manual only"
    assert "push:" in production_triggers and "branches: [main]" in production_triggers
    assert "git reset --hard origin/main" in production, "production smoke must test latest public main"
    assert "production_pwa_smoke.py http" in production
    assert "production_pwa_smoke.py browser" in production
    assert "production_warm_start_smoke.py" in production
    assert "production_pwa_smoke.py http" not in required, "network smoke must not run in PR gate"
    assert "production_pwa_smoke.py browser" not in required, "deployment browser smoke must not run in PR gate"

    assert "node app/data-pipeline.test.mjs" in required, "resilient data pipeline contract is not required before merge"
    assert "node app/date-filter-architecture.test.mjs" in required, "date-filter single-source contract is not required before merge"
    assert "node --check app/sources-toggle.js" in required, "local production shell coverage lost sources module syntax check"


def main() -> None:
    check_single_release_source()
    check_asset_coherence()
    check_manifest_entrypoint()
    check_first_render_contract()
    check_startup_resilience_contract()
    check_workflow_guard()
    print(f"Release guard: OK (release v{release_number()})")


if __name__ == "__main__":
    main()
