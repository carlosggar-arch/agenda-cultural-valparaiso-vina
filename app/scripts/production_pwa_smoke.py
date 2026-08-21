from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
ORIGINS = {
    "github-pages": "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/app/",
    "cloudflare": "https://vivamos.pages.dev/app/",
}
PRIMARY_ORIGIN = "github-pages"

CRITICAL_ASSETS = (
    ("app/index.html", ""),
    ("app/app.js", "app.js"),
    ("app/pwa.js", "pwa.js"),
    ("app/release-version.js", "release-version.js"),
    ("app/service-worker-assets.generated.js", "service-worker-assets.generated.js"),
    ("app/data/venue-registry.json", "data/venue-registry.json"),
    ("app/data/release-bundle.json", "data/release-bundle.json"),
    ("agenda_web.json", "../agenda_web.json"),
    ("app/data/gijon/agenda_web.json", "data/gijon/agenda_web.json"),
    ("fuentes_publicas.json", "../fuentes_publicas.json"),
    ("app/data/source-registry.json", "data/source-registry.json"),
)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def release_number() -> int:
    match = re.search(r"const RELEASE = (\d+);", read("app/release-version.js"))
    if not match:
        raise SystemExit("release-version.js has no numeric RELEASE")
    return int(match.group(1))


def expected_shell() -> dict[str, str]:
    index = read("app/index.html")
    pwa = read("app/pwa.js")
    header = read("app/header-redesign.js")

    header_style = re.search(r'const HEADER_STYLESHEET = "([^"]+)"', header)
    mobile_style = re.search(
        r'<link rel="stylesheet" href="([^"]*mobile-experience\.css[^"]*)" data-mobile-experience-styles>',
        index,
    )
    header_module = re.search(r'import "(\./header-redesign\.js[^\"]*)";', pwa)
    mobile_module = re.search(r'import "(\./mobile-experience\.js[^\"]*)";', pwa)
    if not all((header_style, mobile_style, header_module, mobile_module)):
        raise SystemExit("Unable to derive canonical PWA shell references from local sources")
    return {
        "header_style": header_style.group(1),
        "mobile_style": mobile_style.group(1),
        "header_module": header_module.group(1),
        "mobile_module": mobile_module.group(1),
    }


def canonical_manifest_asset(value: str) -> str:
    return value.split("?", 1)[0]


def manifest_has(manifest: str, value: str) -> bool:
    return f'"{canonical_manifest_asset(value)}"' in manifest


def local_contract() -> None:
    expected = expected_shell()
    index = read("app/index.html")
    app = read("app/app.js")
    pwa = read("app/pwa.js")
    worker = read("app/service-worker.js")
    shell_manifest = read("app/service-worker-assets.generated.js")
    sources = read("app/sources-toggle.js")

    required_index = (
        '<script src="./release-version.js"></script>',
        expected["header_style"],
        expected["mobile_style"],
        "data-header-search-toggle",
        "data-header-search-popover",
    )
    for marker in required_index:
        if marker not in index:
            raise SystemExit(f"Local index is missing: {marker}")

    for marker in (expected["header_module"], expected["mobile_module"]):
        if marker not in pwa:
            raise SystemExit(f"Local pwa.js is missing shell marker: {marker}")

    for marker in (
        "render-lifecycle.js",
        "card-experience.js",
        "card-image-fallback.js",
        "public-presentation-guard.js",
        "exhibition-hours.js",
        "sources-toggle.js",
        "community-source.js",
        "participation-footer.js",
    ):
        if marker not in app:
            raise SystemExit(f"Local app.js is missing content-runtime marker: {marker}")

    forbidden_pwa_runtime_entries = (
        '"./card-experience.js"',
        '"./card-image-fallback.js"',
        '"./public-presentation-guard.js"',
        '"./schedule-display.js',
        '"./exhibition-hours.js',
        '"./sources-toggle.js',
        '"./community-source.js',
        '"./participation-footer.js',
    )
    for marker in forbidden_pwa_runtime_entries:
        if marker in pwa:
            raise SystemExit(f"pwa.js must not instantiate app.js-owned content module: {marker}")

    if "DIAGNOSTIC_SOURCE_META" in sources:
        raise SystemExit("sources-toggle.js must not contain hard-coded per-source metadata")
    for marker in ("canonical_source_id", "eventCountsBySourceId", "runtimeById"):
        if marker not in sources:
            raise SystemExit(f"sources-toggle.js is missing canonical source identity marker: {marker}")

    if "service-worker-assets.generated.js" not in worker:
        raise SystemExit("Local service worker is not wired to the generated shell manifest")
    for marker in (
        "./release-version.js",
        expected["header_style"],
        expected["mobile_style"],
        expected["header_module"],
        expected["mobile_module"],
        "./agenda-runtime-state.mjs",
        "./render-lifecycle.js",
        "./public-presentation-guard.js",
        "./public-presentation-rules.mjs",
    ):
        if not manifest_has(shell_manifest, marker):
            raise SystemExit(f"Generated local shell manifest is missing: {canonical_manifest_asset(marker)}")

    print(f"LOCAL_PWA_SHELL_OK release=v{release_number()} ownership=single canonical_sources=enabled generated_manifest=enabled")


def fetch_bytes(base: str, path: str, timeout: int = 15) -> bytes:
    sep = "&" if "?" in path else "?"
    url = base + path + sep + "smoke=" + uuid.uuid4().hex
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "vivamos-production-smoke/4",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed public HTTPS origins
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read()


def fetch_text(base: str, path: str, timeout: int = 15) -> str:
    return fetch_bytes(base, path, timeout=timeout).decode("utf-8", errors="replace")


def local_hash(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def wait_for_origin_parity(name: str, base: str, attempts: int = 36, interval: int = 10) -> None:
    expected_release = release_number()
    expected_hashes = {remote: local_hash(local) for local, remote in CRITICAL_ASSETS}
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            published_source = fetch_text(base, "release-version.js")
            match = re.search(r"const RELEASE = (\d+);", published_source)
            published = int(match.group(1)) if match else -1
            if published != expected_release:
                last = f"published v{published}, expected v{expected_release}"
            else:
                mismatches = []
                for remote, expected_hash in expected_hashes.items():
                    actual_hash = hashlib.sha256(fetch_bytes(base, remote)).hexdigest()
                    if actual_hash != expected_hash:
                        mismatches.append(remote or "index.html")
                if not mismatches:
                    print(f"PRODUCTION_ORIGIN_PARITY_OK origin={name} release=v{expected_release} assets={len(expected_hashes)}")
                    return
                last = "content mismatch: " + ", ".join(mismatches)
        except Exception as exc:
            last = str(exc)
        if attempt == attempts:
            raise SystemExit(f"{name} did not reach current main parity: {last}")
        time.sleep(interval)


def verify_http_origin(name: str, base: str) -> None:
    expected_release = release_number()
    expected = expected_shell()
    wait_for_origin_parity(name, base)

    index = fetch_text(base, "")
    app = fetch_text(base, "app.js")
    pwa = fetch_text(base, "pwa.js")
    worker = fetch_text(base, "service-worker.js")
    shell_manifest = fetch_text(base, "service-worker-assets.generated.js")

    for marker in (
        '<script src="./release-version.js"></script>',
        expected["header_style"],
        expected["mobile_style"],
        "data-header-search-toggle",
        "data-header-search-popover",
        'data-filter-value="hoy"',
        'data-filter-value="manana"',
        'data-filter-value="fin-de-semana"',
    ):
        if marker not in index:
            raise SystemExit(f"{name} index is missing current shell/filter marker: {marker}")

    for marker in (expected["header_module"], expected["mobile_module"]):
        if marker not in pwa:
            raise SystemExit(f"{name} pwa.js is missing current shell marker: {marker}")

    for marker in ("render-lifecycle.js", "card-experience.js", "public-presentation-guard.js", "sources-toggle.js"):
        if marker not in app:
            raise SystemExit(f"{name} app.js is missing content-runtime marker: {marker}")

    if "service-worker-assets.generated.js" not in worker:
        raise SystemExit(f"{name} service worker is not wired to generated shell manifest")
    for marker in (
        expected["header_style"],
        expected["mobile_style"],
        expected["header_module"],
        expected["mobile_module"],
        "./agenda-runtime-state.mjs",
        "./render-lifecycle.js",
        "./public-presentation-guard.js",
        "./public-presentation-rules.mjs",
    ):
        if not manifest_has(shell_manifest, marker):
            raise SystemExit(f"{name} generated shell manifest is missing current shell marker: {canonical_manifest_asset(marker)}")

    print(f"PUBLISHED_PWA_SHELL_OK origin={name} release=v{expected_release}")


def verify_http() -> None:
    for name, base in ORIGINS.items():
        verify_http_origin(name, base)


def chrome_binary() -> str:
    chrome = next(
        (
            shutil.which(name)
            for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser")
            if shutil.which(name)
        ),
        None,
    )
    if not chrome:
        raise SystemExit("Chrome/Chromium is unavailable on the runner")
    return chrome


def profile_dom(chrome: str, profile: str, base: str, city: str, width: int, height: int, extra: str = "") -> str:
    suffix = f"&{extra.lstrip('&?')}" if extra else ""
    url = f"{base}?city={city}{suffix}&smoke={uuid.uuid4().hex}"
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication",
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={width},{height}",
        "--virtual-time-budget=12000",
        f"--user-data-dir={profile}",
        "--dump-dom",
        url,
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
    if result.returncode == 0 and result.stdout:
        return result.stdout
    raise RuntimeError(result.stderr[-1600:] or f"Chrome exit code {result.returncode} with empty DOM")


def cold_dom(chrome: str, origin: str, base: str, city: str, width: int, height: int) -> str:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-prod-{origin}-{city}-") as profile:
            try:
                return profile_dom(chrome, profile, base, city, width, height)
            except Exception as exc:
                last_error = str(exc)
        if attempt < 2:
            time.sleep(2)
    raise SystemExit(f"Chrome failed for {origin}/{city} {width}x{height} after retry: {last_error}")


def assert_loaded_dom(dom: str, origin: str, city: str, label: str, width: int, height: int, expected_release: int, expected: dict[str, str]) -> None:
    browser_header_style = expected["header_style"].removeprefix("./")
    browser_mobile_style = expected["mobile_style"].removeprefix("./")
    checks = {
        f'data-city="{city}"': "active city was not applied",
        "data-header-redesign=": "header markup disappeared",
        'data-header-search-bound="true"': "static search control was not bound",
        f"PWA v{expected_release}": "visible runtime version is stale",
        label: "city title/label is stale",
        browser_mobile_style: "mobile stylesheet revision is stale",
        browser_header_style: "header stylesheet revision is stale",
        'data-filter-value="hoy"': "Hoy filter disappeared",
        'data-filter-value="manana"': "Mañana filter disappeared",
        'data-filter-value="fin-de-semana"': "Fin de semana filter disappeared",
    }
    for marker, message in checks.items():
        if marker not in dom:
            raise SystemExit(f"{message}: {origin}/{city} {width}x{height}")
    if dom.count('class="event-card') <= 0:
        raise SystemExit(f"No event cards rendered: {origin}/{city} {width}x{height}")
    source_controls = dom.count("data-sources-toggle") + dom.count("data-sources-fallback")
    if source_controls <= 0:
        raise SystemExit(f"Sources control disappeared: {origin}/{city} {width}x{height}")
    if dom.count("data-sources-toggle") > 1:
        raise SystemExit(f"Duplicate sources controls detected: {origin}/{city} {width}x{height}")
    status = re.search(r"data-status[^>]*>(.*?)</", dom, flags=re.S)
    if status and "Preparando la agenda" in html.unescape(re.sub(r"<[^>]+>", "", status.group(1))):
        raise SystemExit(f"Production stayed in loading state: {origin}/{city} {width}x{height}")


def verify_browser() -> None:
    expected_release = release_number()
    expected = expected_shell()
    chrome = chrome_binary()
    cases = (
        ("valparaiso", "Valparaíso / Viña del Mar", 390, 844),
        ("gijon", "Gijón / Xixón", 1280, 900),
    )
    for origin, base in ORIGINS.items():
        for city, label, width, height in cases:
            dom = cold_dom(chrome, origin, base, city, width, height)
            assert_loaded_dom(dom, origin, city, label, width, height, expected_release, expected)
            print(f"PRODUCTION_COLD_LOAD_OK origin={origin} city={city} viewport={width}x{height}")

    # Keep the heavier city roundtrip on the primary origin. The parity check
    # above guarantees Cloudflare serves the same critical assets, while the two
    # cold-load cases still execute its own runtime in Chromium.
    base = ORIGINS[PRIMARY_ORIGIN]
    with tempfile.TemporaryDirectory(prefix="vivamos-roundtrip-") as profile:
        first_valpo = profile_dom(chrome, profile, base, "valparaiso", 390, 844)
        assert_loaded_dom(first_valpo, PRIMARY_ORIGIN, "valparaiso", "Valparaíso / Viña del Mar", 390, 844, expected_release, expected)
        gijon = profile_dom(chrome, profile, base, "gijon", 1280, 900)
        assert_loaded_dom(gijon, PRIMARY_ORIGIN, "gijon", "Gijón / Xixón", 1280, 900, expected_release, expected)
        final_valpo = profile_dom(chrome, profile, base, "valparaiso", 390, 844, "when=7-dias")
        assert_loaded_dom(final_valpo, PRIMARY_ORIGIN, "valparaiso", "Valparaíso / Viña del Mar", 390, 844, expected_release, expected)
        if 'data-card-enhanced="true"' not in final_valpo:
            raise SystemExit("Valpo/Viña rich cards did not recover after Gijón roundtrip")
        if "event-card-photo" not in final_valpo and "event-card-media" not in final_valpo:
            raise SystemExit("Valpo/Viña cards lost image/media presentation after Gijón roundtrip")
        active_seven_days = re.search(
            r'<button[^>]*(?:data-filter-value="7-dias"[^>]*aria-pressed="true"|aria-pressed="true"[^>]*data-filter-value="7-dias")[^>]*>',
            final_valpo,
            flags=re.I,
        )
        if not active_seven_days:
            raise SystemExit("Roundtrip filter state did not apply after returning to Valpo/Viña")
        print("PRODUCTION_CITY_ROUNDTRIP_OK origin=github-pages valparaiso->gijon->valparaiso filter=7-dias")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate local and published ¡Vivamos! PWA parity on GitHub Pages and Cloudflare.")
    parser.add_argument("mode", choices=("local", "http", "browser", "all"))
    args = parser.parse_args()
    if args.mode in {"local", "all"}:
        local_contract()
    if args.mode in {"http", "all"}:
        verify_http()
    if args.mode in {"browser", "all"}:
        verify_browser()


if __name__ == "__main__":
    main()
