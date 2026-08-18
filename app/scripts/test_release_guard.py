from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
WORKFLOW = ROOT / ".github/workflows/multi-city-pre-release.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def release_number() -> int:
    source = text(APP / "release-version.js")
    match = re.search(r"const RELEASE = (\d+);", source)
    assert match, "release-version.js must define a numeric RELEASE"
    return int(match.group(1))


def check_single_release_source() -> None:
    release = release_number()
    index = text(APP / "index.html")
    pwa = text(APP / "pwa.js")
    sw = text(APP / "service-worker.js")

    head = index.split("</head>", 1)[0]
    assert '<script src="./release-version.js"></script>' in head, "release source must load in <head>"
    assert 'globalThis.__VIVAMOS_RELEASE__' in pwa, "PWA must consume the shared release source"
    assert 'importScripts("./release-version.js")' in sw, "service worker must consume the shared release source"
    assert 'const CACHE_VERSION = `v${RELEASE}`' in sw, "cache version must derive from the shared release"
    assert 'service-worker.js?v=${APP_RELEASE}' in pwa, "service-worker registration must derive from the shared release"
    assert '"./release-version.js"' in sw, "release-version.js must be part of the shell cache"

    assert not re.search(r'const APP_VERSION = "PWA v\d+"', pwa), "hard-coded PWA version returned"
    assert not re.search(r'const CACHE_VERSION = "v\d+"', sw), "hard-coded cache version returned"
    assert not re.search(r'service-worker\.js\?v=\d+', pwa), "hard-coded service-worker query version returned"
    assert not re.search(r'data-app-version>PWA v\d+<', index), "HTML footer must not carry a second release number"
    assert release >= 1


def check_asset_coherence() -> None:
    index = text(APP / "index.html")
    pwa = text(APP / "pwa.js")
    sw = text(APP / "service-worker.js")
    header_js = text(APP / "header-redesign.js")
    head = index.split("</head>", 1)[0]

    header_style = re.search(r'const HEADER_STYLESHEET = "([^"]+)"', header_js)
    assert header_style, "header-redesign.js must declare its canonical stylesheet"
    header_style_href = header_style.group(1)
    assert f'<link rel="stylesheet" href="{header_style_href}">' in head, (
        "header stylesheet in <head> must match header-redesign.js before first paint"
    )
    assert f'"{header_style_href}"' in sw, "service-worker shell must cache the canonical header stylesheet"

    mobile_style = re.search(
        r'<link rel="stylesheet" href="(\./mobile-experience\.css[^\"]*)" data-mobile-experience-styles>',
        head,
    )
    assert mobile_style, "mobile CSS must be render-blocking in <head>"
    assert f'"{mobile_style.group(1)}"' in sw, "service-worker shell must cache the exact mobile stylesheet"

    header_module = re.search(r'import "(\./header-redesign\.js[^\"]*)";', pwa)
    mobile_module = re.search(r'import "(\./mobile-experience\.js[^\"]*)";', pwa)
    assert header_module, "pwa.js must import the versioned header module"
    assert mobile_module, "pwa.js must import the versioned mobile module"
    assert f'"{header_module.group(1)}"' in sw, "service worker must cache the exact header module imported by pwa.js"
    assert f'"{mobile_module.group(1)}"' in sw, "service worker must cache the exact mobile module imported by pwa.js"


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
    before_modules = index.split('<script type="module" src="./app.js"></script>', 1)[0]

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


def check_workflow_guard() -> None:
    workflow = text(WORKFLOW)
    assert "python app/scripts/test_release_guard.py" in workflow, "release guard is not wired into CI"
    assert "python app/scripts/test_first_render_browser.py" in workflow, "first-render browser probe is not wired into CI"
    assert 'PWA v33' not in workflow, "stale PWA v33 assertion remains in workflow"
    assert 'CACHE_VERSION = \\"v40\\"' not in workflow and 'CACHE_VERSION = "v40"' not in workflow, (
        "stale cache v40 assertion remains in workflow"
    )


def main() -> None:
    check_single_release_source()
    check_asset_coherence()
    check_manifest_entrypoint()
    check_first_render_contract()
    check_workflow_guard()
    print(f"Release guard: OK (release v{release_number()})")


if __name__ == "__main__":
    main()
