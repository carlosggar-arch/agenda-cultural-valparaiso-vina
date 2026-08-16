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
        + '\n  <script>setTimeout(() => { const root = getComputedStyle(document.documentElement); const card = document.querySelector(".event-card"); const before = card ? getComputedStyle(card, "::before") : null; document.body.dataset.visualBrand = root.getPropertyValue("--brand").trim(); document.body.dataset.visualStripe = before ? before.height : ""; const trigger = document.querySelector("[data-open-event]"); if (trigger) trigger.click(); const detail = document.querySelector("dialog[data-event-detail]"); document.body.dataset.detailOpen = detail && detail.hasAttribute("open") ? "true" : "false"; document.body.dataset.detailHasSource = detail && detail.textContent.includes("Fuente oficial") ? "true" : "false"; }, 6000);</script>'
    )
    if marker not in source or pwa_marker not in source:
        raise AssertionError("app.js/pwa.js script marker not found in app/index.html")
    # Runtime rendering and service-worker lifecycle are separate contracts.
    # Omit pwa.js to avoid activation-triggered navigation, but execute the real
    # presentation modules explicitly so Chrome validates the final card UI.
    source = source.replace(pwa_marker, "", 1)
    TEST_PAGE.write_text(source.replace(marker, injection, 1), encoding="utf-8")


def run_city(city: str, base_url: str) -> None:
    make_test_page(city)
    with tempfile.TemporaryDirectory(prefix=f"agenda-{city}-chrome-") as profile:
        cmd = [
            chrome_binary(),
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--virtual-time-budget=9000",
            f"--user-data-dir={profile}",
            "--dump-dom",
            f"{base_url}/app/__runtime_test.html",
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
        if result.returncode != 0:
            raise AssertionError(
                f"Chrome failed for {city}: exit={result.returncode}\nSTDERR:\n{result.stderr[-4000:]}"
            )
        dom = result.stdout
        card_count = dom.count('class="event-card')
        if card_count <= 0:
            diagnostic = "\n".join(
                line for line in result.stderr.splitlines()
                if "ERROR" in line or "CONSOLE" in line or "Uncaught" in line
            )
            raise AssertionError(
                f"No event cards rendered for {city}. "
                f"DOM contains load error={('No pudimos cargar la agenda' in dom)}.\n"
                f"Chrome diagnostics:\n{diagnostic[-4000:]}\n"
                f"DOM tail:\n{dom[-5000:]}"
            )
        if '<strong data-total="">0</strong>' in dom:
            raise AssertionError(f"Rendered cards but total stayed at zero for {city}")
        if 'class="event-card-media' not in dom:
            raise AssertionError(f"Rich card media did not render for {city}")
        if 'class="event-facts"' not in dom or 'class="card-fact"' not in dom:
            raise AssertionError(f"Date/location/price facts did not render for {city}")
        if 'card-action--primary' not in dom:
            raise AssertionError(f"Primary event action did not render for {city}")
        expected_brand = "#15594f" if city == "valparaiso" else "#12556a"
        if f'data-visual-brand="{expected_brand}"' not in dom:
            raise AssertionError(f"Computed city visual theme did not apply for {city}")
        if 'data-visual-stripe="5px"' not in dom:
            raise AssertionError(f"Computed category card accent did not apply for {city}")
        if 'data-detail-open="true"' not in dom:
            raise AssertionError(f"Internal event detail did not open for {city}")
        if 'data-detail-has-source="true"' not in dom:
            raise AssertionError(f"Internal event detail did not expose the official source for {city}")
        if 'class="event-card-source"' not in dom:
            raise AssertionError(f"Per-card source attribution did not render for {city}")
        if 'class="source-card"' not in dom:
            raise AssertionError(f"City source explorer did not render for {city}")
        if city == "valparaiso" and "Valpo Cultura" not in dom and "Museo Palacio Rioja" not in dom:
            raise AssertionError("Valparaiso/Vina source names did not render")
        if city == "gijon" and "Open Data Ayuntamiento de Gijón/Xixón" not in dom:
            raise AssertionError("Gijon Open Data source did not render")
        if city == "valparaiso":
            if 'data-image-kind="category-fallback"' not in dom:
                raise AssertionError("Valparaiso should replace missing event images with category photos")
            if '../assets/categoria-' not in dom:
                raise AssertionError("Valparaiso category-photo asset did not render")
        if city == "gijon":
            if 'class="event-card-photo"' not in dom:
                raise AssertionError("Gijon should expose at least one official event image")
            if 'data-image-kind="category-fallback"' in dom:
                raise AssertionError("Gijon must not use the Valparaiso category-photo fallback")
        if 'No te lo pierdas' not in dom:
            raise AssertionError(f"Featured editorial badge did not render for {city}")
        print(f"Browser runtime {city}: {card_count} rich cards rendered")


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
