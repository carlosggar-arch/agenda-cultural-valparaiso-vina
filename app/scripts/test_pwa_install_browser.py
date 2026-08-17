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

REQUIRED_MARKERS = {
    'data-pwa-probe-done="true"': "Installed PWA probe did not finish",
    'data-pwa-ready="true"': "Service worker never reached ready state",
    'data-pwa-controlled="true"': "Installed app is not controlled by its service worker after activation",
    'data-pwa-version="PWA v33"': "Installed app did not load the current PWA v33 runtime",
    'data-pwa-still-preparing="false"': "Installed app remained stuck on the loading state",
    'data-mobile-nav-visible="true"': "Mobile one-hand navigation is not visible at phone width",
    'data-mobile-touch-target="true"': "Mobile navigation touch targets are smaller than 44px",
    'data-mobile-city-current="true"': "Current city is not reflected in the mobile city chooser",
    'data-mobile-styles-loaded="true"': "Mobile experience stylesheet did not load",
    'data-mobile-install-meta="true"': "Installed-app title/capable metadata is incomplete",
}

FIRST_OPEN_MARKERS = {
    'data-first-open-done="true"': "First-open probe did not finish",
    'data-first-open-required="true"': "First-open city selection is not mandatory",
    'data-first-open-visible="true"': "First-open chooser is not visible",
    'data-first-open-copy="true"': "First-open chooser copy is not tailored to choosing a city",
    'data-first-open-close-hidden="true"': "First-open chooser can be dismissed before choosing a city",
    'data-first-open-bottom-sheet="true"': "Phone-width chooser is not anchored as a bottom sheet",
    'data-first-open-option-target="true"': "First-open city option is too small for touch",
    'data-first-open-nav-hidden="true"': "Bottom navigation competes visually with first-open chooser",
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
    if '<script type="module" src="./pwa.js"></script>' not in source:
        raise AssertionError("Production pwa.js marker not found")
    return source


def make_test_pages() -> None:
    source = source_index()
    bootstrap = '<script>localStorage.setItem("agenda-cultural-city", "valparaiso");</script>\n  '
    installed_probe = r'''
  <script>
    (() => {
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
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
        const mobileCityButton = document.querySelector('[data-mobile-action="city"]');
        const currentCity = document.querySelector('[data-city-option="valparaiso"][aria-current="true"]');
        const mobileStyles = document.querySelector('link[data-mobile-experience-styles]');
        const navVisible = Boolean(mobileNav && !mobileNav.hidden && getComputedStyle(mobileNav).display !== "none");
        const touchTarget = mobileCityButton ? mobileCityButton.getBoundingClientRect().height >= 44 : false;
        const appleTitle = document.querySelector('meta[name="apple-mobile-web-app-title"]')?.content === "¡Vivamos!";
        const appleCapable = document.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content === "yes";
        const mobileCapable = document.querySelector('meta[name="mobile-web-app-capable"]')?.content === "yes";
        document.body.dataset.pwaProbeDone = "true";
        document.body.dataset.pwaReady = String(ready);
        document.body.dataset.pwaControlled = String(Boolean(navigator.serviceWorker.controller));
        document.body.dataset.pwaCards = String(cards);
        document.body.dataset.pwaVersion = version;
        document.body.dataset.pwaStillPreparing = String(status.includes("Preparando la agenda"));
        document.body.dataset.mobileNavVisible = String(navVisible);
        document.body.dataset.mobileTouchTarget = String(touchTarget);
        document.body.dataset.mobileCityCurrent = String(Boolean(currentCity));
        document.body.dataset.mobileStylesLoaded = String(Boolean(mobileStyles));
        document.body.dataset.mobileInstallMeta = String(appleTitle && appleCapable && mobileCapable);
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
      document.body.dataset.firstOpenNavHidden = String(Boolean(nav?.hidden));
    }, 2600);
  </script>
'''
    # The first-open fixture validates city selection and mobile layout only. Keep the
    # service-worker/install lifecycle exclusive to the installed-PWA fixture so a
    # pending worker cannot keep Chrome --dump-dom alive indefinitely.
    first_open_source = source.replace(
        '<script type="module" src="./pwa.js"></script>',
        '<script type="module" src="./mobile-experience.js"></script>',
        1,
    )
    FIRST_OPEN_PAGE.write_text(first_open_source.replace("</body>", first_open_probe + "\n</body>", 1), encoding="utf-8")


def probe_state(dom: str) -> tuple[bool, str]:
    missing = [message for marker, message in REQUIRED_MARKERS.items() if marker not in dom]
    match = re.search(r'data-pwa-cards="(\d+)"', dom)
    if not match or int(match.group(1)) <= 0:
        missing.append("Installed PWA rendered no event cards")
    observed = ", ".join(re.findall(r'data-(?:pwa|mobile)-[a-z-]+="[^"]*"', dom)[-14:])
    return not missing, f"{'; '.join(missing) or 'ready'}; observed: {observed or 'no probe attributes'}"


def first_open_state(dom: str) -> tuple[bool, str]:
    missing = [message for marker, message in FIRST_OPEN_MARKERS.items() if marker not in dom]
    observed = ", ".join(re.findall(r'data-first-open-[a-z-]+="[^"]*"', dom)[-10:])
    return not missing, f"{'; '.join(missing) or 'ready'}; observed: {observed or 'no first-open attributes'}"


def chrome_command(url: str, profile: str, budget: int) -> list[str]:
    return [
        chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--disable-background-networking",
        "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
        "--deny-permission-prompts",
        "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
        "--window-size=390,844", f"--virtual-time-budget={budget}",
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


def run_first_open(url: str) -> str:
    errors: list[str] = []
    for attempt in range(1, 4):
        with tempfile.TemporaryDirectory(prefix=f"agenda-first-open-{attempt}-", ignore_cleanup_errors=True) as profile:
            try:
                result = subprocess.run(chrome_command(url, profile, 6000), cwd=ROOT, text=True, capture_output=True, timeout=40)
            except subprocess.TimeoutExpired:
                errors.append(f"attempt {attempt}: Chrome timed out")
                time.sleep(1)
                continue
            if result.returncode != 0 or not result.stdout:
                errors.append(f"attempt {attempt}: exit={result.returncode}; stderr={result.stderr[-1200:]}")
                time.sleep(1)
                continue
            ok, state = first_open_state(result.stdout)
            if ok:
                return result.stdout
            errors.append(f"attempt {attempt}: {state}")
            time.sleep(1)
    raise AssertionError(f"First-open Chrome probe failed after three isolated attempts: {' | '.join(errors)}")


def main() -> None:
    os.chdir(ROOT)
    make_test_pages()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); time.sleep(0.2)
        try:
            first_open_dom = run_first_open(f"http://127.0.0.1:{port}/app/__pwa_first_open_test.html")
            dom = run_chrome(f"http://127.0.0.1:{port}/app/__pwa_install_test.html")
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
    print(f"Mobile PWA test: first-open chooser, install metadata, one-hand navigation, touch targets and {match.group(1)} Valparaiso cards validated")


if __name__ == "__main__":
    main()