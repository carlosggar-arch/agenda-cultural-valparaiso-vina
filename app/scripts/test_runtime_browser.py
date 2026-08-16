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
TEST_PAGE = APP / "__runtime_test.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def make_test_page(city: str) -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    marker = '<script type="module" src="./app.js"></script>'
    pwa_marker = '<script type="module" src="./pwa.js"></script>'
    injection = (
        f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>\n  '
        + marker
        + '\n  <script type="module" src="./card-experience.js"></script>'
        + '\n  <script type="module" src="./card-image-fallback.js"></script>'
        + '\n  <script type="module" src="./compact-top.js"></script>'
        + '\n  <script type="module" src="./gijon-visual-reference.js"></script>'
        + '\n  <script type="module" src="./lean-filters.js"></script>'
        + '\n  <script type="module" src="./sources-toggle.js"></script>'
        + '\n  <script>setTimeout(() => { const quickFilters = [...document.querySelectorAll("[data-section-filter]")].map((button) => button.dataset.sectionFilter); const activeQuick = document.querySelector("[data-section-filter][aria-pressed=\"true\"]"); const sourceSection = document.querySelector("[data-sources-section]"); const sourceToggle = document.querySelector("[data-sources-toggle]"); document.body.dataset.gijonVisualReference = document.querySelector("[data-gijon-visual-reference]") ? "true" : "false"; document.body.dataset.quickFilters = quickFilters.join(","); document.body.dataset.activeQuickFilter = activeQuick?.dataset.sectionFilter || ""; document.body.dataset.sourcesDefaultHidden = sourceSection && getComputedStyle(sourceSection).display === "none" ? "true" : "false"; if (sourceToggle) sourceToggle.click(); document.body.dataset.sourcesAfterOpen = sourceSection && getComputedStyle(sourceSection).display !== "none" ? "true" : "false"; const trigger = document.querySelector("[data-open-event]"); if (trigger) trigger.click(); const detail = document.querySelector("dialog[data-event-detail]"); document.body.dataset.detailOpen = detail && detail.hasAttribute("open") ? "true" : "false"; document.body.dataset.detailHasSource = detail && detail.textContent.includes("Fuente oficial") ? "true" : "false"; }, 6000);</script>'
    )
    if marker not in source or pwa_marker not in source:
        raise AssertionError("app.js/pwa.js script marker not found in app/index.html")
    source = source.replace(pwa_marker, "", 1)
    TEST_PAGE.write_text(source.replace(marker, injection, 1), encoding="utf-8")


def run_city(city: str, base_url: str) -> None:
    make_test_page(city)
    with tempfile.TemporaryDirectory(prefix=f"agenda-{city}-chrome-") as profile:
        cmd = [
            chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-background-networking",
            "--virtual-time-budget=9000", f"--user-data-dir={profile}", "--dump-dom",
            f"{base_url}/app/__runtime_test.html",
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
        if result.returncode != 0:
            raise AssertionError(f"Chrome failed for {city}: exit={result.returncode}\nSTDERR:\n{result.stderr[-4000:]}")
        dom = result.stdout
        card_count = dom.count('class="event-card')
        if card_count <= 0:
            raise AssertionError(f"No event cards rendered for {city}. DOM tail:\n{dom[-5000:]}")
        if f'data-city="{city}"' not in dom:
            raise AssertionError(f"Active city context did not apply for {city}")
        for marker, message in (
            ('data-quick-filters="hoy,fin-de-semana,terminan-pronto,gratis,todos"', "Quick filters are not limited to time/free controls"),
            ('data-sources-default-hidden="true"', "Agenda sources are visible without explicit user action"),
            ('data-sources-after-open="true"', "Agenda sources did not open after explicit user action"),
            ('data-detail-open="true"', "Internal event detail did not open"),
            ('data-detail-has-source="true"', "Internal event detail did not expose source"),
        ):
            if marker not in dom:
                raise AssertionError(f"{message} for {city}")
        if 'data-active-quick-filter=""' in dom:
            raise AssertionError(f"No visible quick filter is active for {city}")
        if 'class="event-card-source"' not in dom or 'class="source-card"' not in dom:
            raise AssertionError(f"Source data did not remain available for {city}")
        if city == "gijon":
            if 'data-gijon-visual-reference="true"' not in dom or "https://www.gijon.es/app/actividades/oferta" not in dom:
                raise AssertionError("Gijon official visual activity reference did not render")
        elif 'data-gijon-visual-reference="true"' in dom:
            raise AssertionError("Gijon visual reference leaked into Valparaiso")
        if city == "valparaiso" and 'data-image-kind="category-fallback"' not in dom:
            raise AssertionError("Valparaiso should replace missing images with category photos")
        if city == "gijon" and 'class="event-card-photo"' not in dom:
            raise AssertionError("Gijon should expose at least one official event image")
        if 'No te lo pierdas' not in dom:
            raise AssertionError(f"Featured editorial badge did not render for {city}")
        print(f"Browser runtime {city}: {card_count} rich cards rendered with lean controls and opt-in sources")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            for city in ("valparaiso", "gijon"):
                run_city(city, f"http://127.0.0.1:{port}")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
