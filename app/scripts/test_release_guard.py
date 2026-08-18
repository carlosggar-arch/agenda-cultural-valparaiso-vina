from __future__ import annotations

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


def check_first_render_contract() -> None:
    index = text(APP / "index.html")
    mobile = text(APP / "mobile-experience.js")
    head = index.split("</head>", 1)[0]
    before_modules = index.split('<script type="module" src="./app.js"></script>', 1)[0]

    assert '<link rel="stylesheet" href="./mobile-experience.css?v=20260817-topcontrols2" data-mobile-experience-styles>' in head, (
        "mobile CSS must be render-blocking in <head>"
    )
    assert 'document.createElement("link")' not in mobile, "mobile CSS must never be injected after first paint"
    assert 'document.head.append(link)' not in mobile, "mobile CSS must never be appended dynamically"

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
    check_first_render_contract()
    check_workflow_guard()
    print(f"Release guard: OK (release v{release_number()})")


if __name__ == "__main__":
    main()
