from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__schedule_interaction_test.html"


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
    pwa_marker = '<script type="module" src="./pwa.js"></script>'
    if pwa_marker not in source:
        raise AssertionError("pwa.js script marker not found in app/index.html")

    # app.js remains the single owner of card, schedule and image presentation.
    # This fixture replaces only pwa.js so it can exercise shell interactions
    # without registering a service worker or duplicating presentation owners.
    enhancement_stack = '''<script type="module">
      import "./vivamos-brand.js";
      import "./compact-top.js";
      import "./gijon-visual-reference.js";
      import "./sources-toggle.js";
      import "./community-source.js";
      import "./header-redesign.js";
      import "./density-polish.js";
      import "./combined-filters-polish.js";
    </script>
    <script>
      setTimeout(() => {
        const citySwitch = document.querySelector("[data-city-switch]");
        const chooser = document.querySelector("[data-chooser-backdrop]");
        const valpoMedia = document.querySelectorAll(".event-card-media").length;
        document.body.dataset.valpoMediaBeforeSwitch = String(valpoMedia);

        citySwitch?.click();
        document.body.dataset.cityChooserOpened = chooser && !chooser.hidden ? "true" : "false";

        const gijon = document.querySelector('[data-city-option="gijon"]');
        gijon?.click();

        setTimeout(() => {
          document.body.dataset.cityAfterSwitch = document.documentElement.dataset.city || "";
          document.body.dataset.gijonMediaAfterSwitch = String(
            document.querySelectorAll(".event-card-media").length,
          );
          const searchToggle = document.querySelector("[data-header-search-toggle]");
          const searchPopover = document.querySelector("[data-header-search-popover]");
          searchToggle?.click();
          document.body.dataset.searchResponsive = searchPopover && !searchPopover.hidden ? "true" : "false";
          document.body.dataset.interactionTestDone = "true";
        }, 2800);
      }, 5200);
    </script>'''

    bootstrap = '<script>localStorage.setItem("agenda-cultural-city", "valparaiso");</script>\n  '
    source = source.replace("<body>", "<body>\n  " + bootstrap, 1)
    TEST_PAGE.write_text(source.replace(pwa_marker, enhancement_stack, 1), encoding="utf-8")


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)

    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            with tempfile.TemporaryDirectory(prefix="agenda-schedule-interaction-", ignore_cleanup_errors=True) as profile:
                cmd = [
                    chrome_binary(),
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--disable-background-networking",
                    "--disable-extensions",
                    "--disable-sync",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
                    "--virtual-time-budget=11000",
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    f"http://127.0.0.1:{port}/app/__schedule_interaction_test.html",
                ]
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
                if result.returncode != 0:
                    raise AssertionError(
                        "Chrome did not complete the interaction test; a self-triggering "
                        f"observer may have frozen the event loop. exit={result.returncode}\n"
                        f"STDERR:\n{result.stderr[-4000:]}"
                    )
                dom = result.stdout
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)

    required = {
        'data-interaction-test-done="true"': "The browser timer never completed",
        'data-city-chooser-opened="true"': "Changing city did not open the chooser",
        'data-city-after-switch="gijon"': "The city did not switch from Valparaiso to Gijon",
        'data-search-responsive="true"': "Header interaction stopped responding after the switch",
    }
    for marker, message in required.items():
        if marker not in dom:
            raise AssertionError(f"{message}. DOM tail:\n{dom[-5000:]}")

    import re

    valpo_match = re.search(r'data-valpo-media-before-switch="(\d+)"', dom)
    gijon_match = re.search(r'data-gijon-media-after-switch="(\d+)"', dom)
    if not valpo_match or int(valpo_match.group(1)) <= 0:
        raise AssertionError("Valparaiso canonical presentation did not render event media")
    if not gijon_match or int(gijon_match.group(1)) <= 0:
        raise AssertionError("Gijon canonical presentation did not render event media after city switch")

    print("City-switch browser scenario: UI responsive and media preserved across Valparaiso → Gijon")


if __name__ == "__main__":
    main()
