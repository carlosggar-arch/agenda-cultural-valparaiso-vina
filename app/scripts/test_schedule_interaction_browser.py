from __future__ import annotations

import http.server
import os
import socketserver
import tempfile
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__schedule_interaction_test.html"
WAIT_SECONDS = 30


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def make_test_page() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    pwa_marker = '<script type="module" src="./pwa.js"></script>'
    if pwa_marker not in source:
        raise AssertionError("pwa.js script marker not found in app/index.html")

    # app.js remains the single owner of card, schedule and content presentation.
    # This fixture replaces only pwa.js and loads shell-only helpers that pwa.js
    # normally owns. Do not import sources/community modules here: app.js already
    # owns them and a second module URL would instantiate duplicate observers.
    enhancement_stack = '''<script type="module">
      import "./vivamos-brand.js";
      import "./compact-top.js";
      import "./gijon-visual-reference.js";
      import "./header-redesign.js";
      import "./density-polish.js";
      import "./combined-filters-polish.js";
    </script>'''

    TEST_PAGE.write_text(source.replace(pwa_marker, enhancement_stack, 1), encoding="utf-8")


def chrome_options(profile: str) -> Options:
    options = Options()
    options.page_load_strategy = "eager"
    for argument in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,900",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(argument)
    return options


def js_bool(driver: webdriver.Chrome, expression: str) -> bool:
    return bool(driver.execute_script(f"return Boolean({expression});"))


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)

    with ThreadingServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="agenda-schedule-interaction-", ignore_cleanup_errors=True) as profile:
                driver = webdriver.Chrome(options=chrome_options(profile))
                try:
                    driver.get(f"http://127.0.0.1:{port}/app/__schedule_interaction_test.html?city=valparaiso")
                    wait = WebDriverWait(driver, WAIT_SECONDS, poll_frequency=0.05)

                    wait.until(lambda current: js_bool(
                        current,
                        "document.documentElement.dataset.vivamosReady === 'true'",
                    ))
                    wait.until(lambda current: current.execute_script(
                        "return document.querySelectorAll('.event-card-media').length;"
                    ) > 0)
                    valpo_media = int(driver.execute_script(
                        "return document.querySelectorAll('.event-card-media').length;"
                    ))

                    driver.execute_script("document.querySelector('[data-city-switch]')?.click();")
                    wait.until(lambda current: js_bool(
                        current,
                        "document.querySelector('[data-chooser-backdrop]') && !document.querySelector('[data-chooser-backdrop]').hidden",
                    ))

                    driver.execute_script(
                        "document.querySelector('[data-city-option=\"gijon\"]')?.click();"
                    )
                    wait.until(lambda current: current.execute_script(
                        "return document.documentElement.dataset.city || '';"
                    ) == "gijon")
                    wait.until(lambda current: js_bool(
                        current,
                        "document.documentElement.dataset.vivamosReady === 'true'",
                    ))
                    wait.until(lambda current: current.execute_script(
                        "return document.querySelectorAll('.event-card-media').length;"
                    ) > 0)
                    gijon_media = int(driver.execute_script(
                        "return document.querySelectorAll('.event-card-media').length;"
                    ))

                    driver.execute_script(
                        "document.querySelector('[data-header-search-toggle]')?.click();"
                    )
                    wait.until(lambda current: js_bool(
                        current,
                        "document.querySelector('[data-header-search-popover]') && !document.querySelector('[data-header-search-popover]').hidden",
                    ))

                    sources_toggle_count = int(driver.execute_script(
                        "return document.querySelectorAll('[data-sources-toggle]').length;"
                    ))
                    if sources_toggle_count > 1:
                        raise AssertionError(
                            f"Content ownership regressed: {sources_toggle_count} source toggles were mounted"
                        )
                    if valpo_media <= 0:
                        raise AssertionError("Valparaiso canonical presentation did not render event media")
                    if gijon_media <= 0:
                        raise AssertionError("Gijon canonical presentation did not render event media after city switch")
                finally:
                    driver.quit()
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)

    print(
        "City-switch browser scenario: UI responsive and media preserved across "
        "Valparaiso → Gijon; single content ownership preserved"
    )


if __name__ == "__main__":
    main()
