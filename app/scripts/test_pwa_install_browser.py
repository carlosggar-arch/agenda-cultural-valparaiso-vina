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

REQUIRED_MARKERS = {
    'data-pwa-probe-done="true"': "Installed PWA probe did not finish",
    'data-pwa-ready="true"': "Service worker never reached ready state",
    'data-pwa-controlled="true"': "Installed app is not controlled by its service worker after activation",
    'data-pwa-version="PWA v29"': "Installed app did not load the current PWA v29 runtime",
    'data-pwa-still-preparing="false"': "Installed app remained stuck on the loading state",
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


def make_test_page() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    if '<script type="module" src="./pwa.js"></script>' not in source:
        raise AssertionError("Production pwa.js marker not found")
    bootstrap = '<script>localStorage.setItem("agenda-cultural-city", "valparaiso");</script>\n  '
    probe = r'''
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
        document.body.dataset.pwaProbeDone = "true";
        document.body.dataset.pwaReady = String(ready);
        document.body.dataset.pwaControlled = String(Boolean(navigator.serviceWorker.controller));
        document.body.dataset.pwaCards = String(cards);
        document.body.dataset.pwaVersion = version;
        document.body.dataset.pwaStillPreparing = String(status.includes("Preparando la agenda"));
      };
      probe();
    })();
  </script>
'''
    source = source.replace("<body>", "<body>\n  " + bootstrap, 1)
    source = source.replace("</body>", probe + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def probe_state(dom: str) -> tuple[bool, str]:
    missing = [message for marker, message in REQUIRED_MARKERS.items() if marker not in dom]
    match = re.search(r'data-pwa-cards="(\d+)"', dom)
    if not match or int(match.group(1)) <= 0:
        missing.append("Installed PWA rendered no event cards")
    observed = ", ".join(re.findall(r'data-pwa-[a-z-]+="[^"]*"', dom)[-8:])
    return not missing, f"{'; '.join(missing) or 'ready'}; observed: {observed or 'no probe attributes'}"


def run_chrome(url: str) -> str:
    errors: list[str] = []
    # A headless Chromium process may render the app before service-worker
    # activation settles even though the runtime itself is healthy. Treat the
    # complete installed-PWA contract as the retry condition, not just process exit.
    for attempt in range(1, 4):
        with tempfile.TemporaryDirectory(prefix=f"agenda-installed-pwa-{attempt}-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
                "--virtual-time-budget=18000", f"--user-data-dir={profile}", "--dump-dom", url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=50)
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


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); time.sleep(0.2)
        try:
            dom = run_chrome(f"http://127.0.0.1:{port}/app/__pwa_install_test.html")
        finally:
            server.shutdown(); thread.join(timeout=2); TEST_PAGE.unlink(missing_ok=True)

    ok, state = probe_state(dom)
    if not ok:
        raise AssertionError(state)
    match = re.search(r'data-pwa-cards="(\d+)"', dom)
    assert match is not None
    print(f"Installed PWA browser test: service worker active and {match.group(1)} Valparaiso cards rendered")


if __name__ == "__main__":
    main()
