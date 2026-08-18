from __future__ import annotations

import http.server
import os
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__pwa_install_test.html"
FIRST_OPEN_PAGE = APP / "__pwa_first_open_test.html"
HEADLESS_MOBILE_WIDTH = 500  # Chromium headless en GitHub Actions no baja de este ancho CSS.
PWA_JS = (APP / "pwa.js").read_text(encoding="utf-8")
PWA_VERSION_MATCH = re.search(r'const APP_VERSION = "(PWA v\d+)"', PWA_JS)
if not PWA_VERSION_MATCH:
    raise AssertionError("Current PWA version marker not found in app/pwa.js")
EXPECTED_PWA_VERSION = PWA_VERSION_MATCH.group(1)

REQUIRED_MARKERS = {
    'data-pwa-probe-done="true"': "Installed PWA probe did not finish",
    'data-pwa-ready="true"': "Service worker never reached ready state",
    'data-pwa-controlled="true"': "Installed app is not controlled by its service worker after activation",
    f'data-pwa-version="{EXPECTED_PWA_VERSION}"': f"Installed app did not load the current {EXPECTED_PWA_VERSION} runtime",
    'data-pwa-still-preparing="false"': "Installed app remained stuck on the loading state",
    'data-mobile-nav-absent="true"': "Removed bottom navigation was reintroduced",
    'data-mobile-city-current="true"': "Current city is not reflected in the city chooser",
    'data-mobile-styles-loaded="true"': "Mobile experience stylesheet did not load",
    'data-mobile-install-meta="true"': "Installed-app title/capable metadata is incomplete",
}

HEADER_LAYOUT_MARKERS = {
    'data-header-layout-done="true"': "Mobile header layout probe did not finish",
    'data-header-no-title-overlap="true"': "Header actions overlap the city title/tagline",
    'data-header-actions-in-viewport="true"': "A header action leaves the mobile viewport",
    'data-header-touch-targets="true"': "A persistent header action is too small for touch",
    'data-header-qr-present="true"': "QR share action is missing",
    'data-header-city-present="true"': "City switch action is missing",
    'data-header-favorites-present="true"': "Mis planes action is missing",
    'data-header-search-present="true"': "Search action is missing",
    'data-header-install-visible="true"': "Install action is not visible in first-visit simulation",
    'data-header-install-second-row="true"': "Install action is not isolated on the second mobile row",
}

FIRST_OPEN_MARKERS = {
    'data-first-open-done="true"': "First-open probe did not finish",
    'data-first-open-required="true"': "First-open city selection is not mandatory",
    'data-first-open-visible="true"': "First-open chooser is not visible",
    'data-first-open-copy="true"': "First-open chooser copy is not tailored to choosing a city",
    'data-first-open-close-hidden="true"': "First-open chooser can be dismissed before choosing a city",
    'data-first-open-bottom-sheet="true"': "Phone-width chooser is not anchored as a bottom sheet",
    'data-first-open-option-target="true"': "First-open city option is too small for touch",
    'data-first-open-nav-absent="true"': "Removed bottom navigation competes with first-open chooser",
}


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def source_index() -> str:
    source = (APP / "index.html").read_text(encoding="utf-8")
    if not re.search(r'<script type="module" src="\./pwa\.js(?:\?v=[^"]+)?"></script>', source):
        raise AssertionError("Production pwa.js marker not found")
    return source


def assert_narrow_header_css_contract() -> None:
    css = (APP / "share-qr.css").read_text(encoding="utf-8")
    required = (
        "@media(max-width:700px)",
        "grid-template-rows:auto auto!important",
        ".app-header > .header-bottom",
        "grid-template-columns:repeat(4,max-content)!important",
        ".header-actions .install-button",
        "grid-column:1 / -1",
        "grid-row:2",
        "@media(max-width:430px)",
        "max-width:calc(100vw - 66px)!important",
    )
    for marker in required:
        assert marker in css, f"Missing narrow-header CSS contract: {marker}"


def make_test_pages() -> None:
    source = source_index()
    bootstrap = '<script>localStorage.setItem("agenda-cultural-city", "valparaiso");</script>\n  '
    installed_probe = r'''
  <script>
    (() => {
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const overlaps = (a, b) => Boolean(a && b && a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top);
      const probe = async () => {
        await sleep(7500);
        let ready = false;
        try {
          await Promise.race([
            navigator.serviceWorker.ready,
            sleep(4000).then(() => { throw new Error("service-worker-ready-timeout"); }),
          ]);
          ready = true;
        } catch {}
        const cards = document.querySelectorAll(".event-card[data-event-id]").length;
        const version = document.querySelector("[data-app-version]")?.textContent?.trim() || "";
        const status = document.querySelector("[data-status]")?.textContent?.trim() || "";
        const mobileNav = document.querySelector("[data-mobile-tabbar]");
        const currentCity = document.querySelector('[data-city-option="valparaiso"][aria-current="true"]');
        const mobileStyles = document.querySelector('link[data-mobile-experience-styles]');
        const appleTitle = document.querySelector('meta[name="apple-mobile-web-app-title"]')?.content === "¡Vivamos!";
        const appleCapable = document.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content === "yes";
        const mobileCapable = document.querySelector('meta[name="mobile-web-app-capable"]')?.content === "yes";
        document.body.dataset.pwaProbeDone = "true";
        document.body.dataset.pwaReady = String(ready);
        document.body.dataset.pwaControlled = String(Boolean(navigator.serviceWorker.controller));
        document.body.dataset.pwaCards = String(cards);
        document.body.dataset.pwaVersion = version;
        document.body.dataset.pwaStillPreparing = String(status.includes("Preparando la agenda"));
        document.body.dataset.mobileNavAbsent = String(!mobileNav);
        document.body.dataset.mobileCityCurrent = String(Boolean(currentCity));
        document.body.dataset.mobileStylesLoaded = String(Boolean(mobileStyles));
        document.body.dataset.mobileInstallMeta = String(appleTitle && appleCapable && mobileCapable);

        const forceInstall = new URL(location.href).searchParams.get("install") === "1";
        const install = document.querySelector("[data-install-app]");
        if (forceInstall && install) install.hidden = false;
        await sleep(80);
        const actions = document.querySelector(".header-actions");
        const title = document.querySelector("[data-header-city-title]");
        const tagline = document.querySelector(".header-tagline");
        const qr = document.querySelector("[data-share-qr-open]");
        const city = document.querySelector("[data-city-switch]");
        const favorites = document.querySelector("[data-favorites-access]");
        const search = document.querySelector("[data-header-search-toggle]");
        const visibleActions = actions ? [...actions.children].filter((node) => {
          const style = getComputedStyle(node);
          const rect = node.getBoundingClientRect();
          return !node.hidden && style.display !== "none" && rect.width > 0 && rect.height > 0;
        }) : [];
        const titleRect = title?.getBoundingClientRect();
        const taglineRect = tagline?.getBoundingClientRect();
        const noTitleOverlap = visibleActions.every((node) => {
          const rect = node.getBoundingClientRect();
          return !overlaps(rect, titleRect) && !overlaps(rect, taglineRect);
        });
        const inViewport = visibleActions.every((node) => {
          const rect = node.getBoundingClientRect();
          return rect.left >= -1 && rect.right <= window.innerWidth + 1;
        });
        const persistent = [favorites, search, qr, city].filter(Boolean);
        const touchTargets = persistent.length === 4 && persistent.every((node) => {
          const rect = node.getBoundingClientRect();
          return rect.width >= 34 && rect.height >= 34;
        });
        const installRect = install?.getBoundingClientRect();
        const firstRowBottom = Math.max(...persistent.map((node) => node.getBoundingClientRect().bottom), 0);
        document.body.dataset.headerLayoutDone = "true";
        document.body.dataset.headerNoTitleOverlap = String(noTitleOverlap);
        document.body.dataset.headerActionsInViewport = String(inViewport);
        document.body.dataset.headerTouchTargets = String(touchTargets);
        document.body.dataset.headerQrPresent = String(Boolean(qr));
        document.body.dataset.headerCityPresent = String(Boolean(city));
        document.body.dataset.headerFavoritesPresent = String(Boolean(favorites));
        document.body.dataset.headerSearchPresent = String(Boolean(search));
        document.body.dataset.headerInstallVisible = String(Boolean(install && !install.hidden && getComputedStyle(install).display !== "none"));
        document.body.dataset.headerInstallSecondRow = String(Boolean(installRect && installRect.top >= firstRowBottom - 1));
        document.body.dataset.headerViewportWidth = String(window.innerWidth);
      };
      probe();
    })();
  </script>
'''
    installed_source = source.replace("<body>", "<body>\n  " + bootstrap, 1)
    TEST_PAGE.write_text(installed_source.replace("</body>", installed_probe + "\n</body>", 1), encoding="utf-8")

    first_open_probe = r'''
  <script>
    setTimeout(() => {
      const backdrop = document.querySelector("[data-chooser-backdrop]");
      const chooser = document.querySelector("[data-chooser]");
      const close = document.querySelector("[data-chooser-close]");
      const title = document.querySelector("#chooser-title")?.textContent?.trim() || "";
      const option = document.querySelector('[data-city-option="valparaiso"]');
      const nav = document.querySelector("[data-mobile-tabbar]");
      const rect = chooser?.getBoundingClientRect();
      const bottomSheet = Boolean(rect && Math.abs(rect.bottom - window.innerHeight) <= 2);
      document.body.dataset.firstOpenDone = "true";
      document.body.dataset.firstOpenRequired = String(backdrop?.dataset.selectionRequired === "true");
      document.body.dataset.firstOpenVisible = String(Boolean(backdrop && !backdrop.hidden));
      document.body.dataset.firstOpenCopy = String(title.includes("Dónde quieres descubrir planes"));
      document.body.dataset.firstOpenCloseHidden = String(Boolean(close?.hidden));
      document.body.dataset.firstOpenBottomSheet = String(bottomSheet);
      document.body.dataset.firstOpenOptionTarget = String(Boolean(option && option.getBoundingClientRect().height >= 72));
      document.body.dataset.firstOpenNavAbsent = String(!nav);
    }, 2600);
  </script>
'''
    FIRST_OPEN_PAGE.write_text(source.replace("</body>", first_open_probe + "\n</body>", 1), encoding="utf-8")


def marker_state(dom: str, markers: dict[str, str], pattern: str) -> tuple[bool, str]:
    missing = [message for marker, message in markers.items() if marker not in dom]
    observed = ", ".join(re.findall(pattern, dom)[-16:])
    return not missing, f"{'; '.join(missing) or 'ready'}; observed: {observed or 'no probe attributes'}"


def probe_state(dom: str) -> tuple[bool, str]:
    ok, state = marker_state(dom, REQUIRED_MARKERS, r'data-(?:pwa|mobile)-[a-z-]+="[^"]*"')
    match = re.search(r'data-pwa-cards="(\d+)"', dom)
    if not match or int(match.group(1)) <= 0:
        return False, f"Installed PWA rendered no event cards; {state}"
    return ok, state


def header_layout_state(dom: str) -> tuple[bool, str]:
    ok, state = marker_state(dom, HEADER_LAYOUT_MARKERS, r'data-header-[a-z-]+="[^"]*"')
    width_match = re.search(r'data-header-viewport-width="(\d+)"', dom)
    if not width_match:
        return False, f"Missing observed viewport width; {state}"
    observed_width = int(width_match.group(1))
    if observed_width > HEADLESS_MOBILE_WIDTH + 1:
        return False, f"Runner left the intended mobile breakpoint: {observed_width}px; {state}"
    return ok, state


def first_open_state(dom: str) -> tuple[bool, str]:
    return marker_state(dom, FIRST_OPEN_MARKERS, r'data-first-open-[a-z-]+="[^"]*"')


def chrome_command(url: str, profile: str, budget: int, width: int = HEADLESS_MOBILE_WIDTH, height: int = 844) -> list[str]:
    return [
        chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--disable-background-networking",
        "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
        "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
        f"--window-size={width},{height}", f"--virtual-time-budget={budget}",
        f"--user-data-dir={profile}", "--dump-dom", url,
    ]


def run_chrome(url: str) -> str:
    errors: list[str] = []
    for attempt in range(1, 4):
        with tempfile.TemporaryDirectory(prefix=f"agenda-installed-pwa-{attempt}-", ignore_cleanup_errors=True) as profile:
            try:
                result = subprocess.run(chrome_command(url, profile, 18000), cwd=ROOT, text=True, capture_output=True, timeout=50)
            except subprocess.TimeoutExpired:
                errors.append(f"attempt {attempt}: Chrome timed out")
                time.sleep(1)
                continue
            if result.returncode != 0 or not result.stdout:
                errors.append(f"attempt {attempt}: exit={result.returncode}; stderr={result.stderr[-1200:]}")
                time.sleep(1)
                continue
            ok, state = probe_state(result.stdout)
            if ok:
                return result.stdout
            errors.append(f"attempt {attempt}: {state}")
            time.sleep(1)
    raise AssertionError(f"Installed-PWA probe failed after three isolated attempts: {' | '.join(errors)}")


def run_header_layout(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="agenda-mobile-header-", ignore_cleanup_errors=True) as profile:
        result = subprocess.run(chrome_command(url, profile, 18000), cwd=ROOT, text=True, capture_output=True, timeout=50)
    if result.returncode != 0 or not result.stdout:
        raise AssertionError(f"Header Chrome probe failed: exit={result.returncode}; stderr={result.stderr[-1200:]}")
    ok, state = header_layout_state(result.stdout)
    if not ok:
        raise AssertionError(f"Header layout failed: {state}")
    return result.stdout


def run_first_open(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="agenda-first-open-", ignore_cleanup_errors=True) as profile:
        result = subprocess.run(chrome_command(url, profile, 6000), cwd=ROOT, text=True, capture_output=True, timeout=30)
    if result.returncode != 0 or not result.stdout:
        raise AssertionError(f"First-open Chrome probe failed: exit={result.returncode}; stderr={result.stderr[-1200:]}")
    ok, state = first_open_state(result.stdout)
    if not ok:
        raise AssertionError(state)
    return result.stdout


def main() -> None:
    os.chdir(ROOT)
    assert_narrow_header_css_contract()
    make_test_pages()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); time.sleep(0.2)
        try:
            first_open_dom = run_first_open(f"http://127.0.0.1:{port}/app/__pwa_first_open_test.html")
            dom = run_chrome(f"http://127.0.0.1:{port}/app/__pwa_install_test.html")
            run_header_layout(f"http://127.0.0.1:{port}/app/__pwa_install_test.html?install=1")
        finally:
            server.shutdown(); thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True); FIRST_OPEN_PAGE.unlink(missing_ok=True)

    ok, state = first_open_state(first_open_dom)
    if not ok:
        raise AssertionError(state)
    ok, state = probe_state(dom)
    if not ok:
        raise AssertionError(state)
    match = re.search(r'data-pwa-cards="(\d+)"', dom)
    assert match is not None
    print(
        "Mobile PWA test: first-open chooser, installed shell, live mobile-breakpoint header, "
        "and 320/390/430 narrow CSS contract validated; "
        f"{match.group(1)} Valparaiso cards rendered"
    )


if __name__ == "__main__":
    main()
