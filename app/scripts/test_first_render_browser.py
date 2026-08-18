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
TEST_PAGE = APP / "__first_render_test.html"


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
    release_marker = '<script src="./release-version.js"></script>'
    assert release_marker in source, "release-version.js must load before first-render bootstrap"

    preload = f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>'
    source = source.replace(release_marker, release_marker + "\n  " + preload, 1)
    source = re.sub(r'\s*<script type="module" src="[^"]+"></script>', "", source)

    diagnostic = r'''
  <script>
    (() => {
      const header = document.querySelector(".app-header");
      const title = document.querySelector("[data-header-city-title]");
      const hero = document.querySelector(".hero");
      const art = document.querySelector(".header-art");
      const bottom = document.querySelector(".header-bottom");
      const mobileSheet = [...document.styleSheets].some((sheet) => String(sheet.href || "").includes("mobile-experience.css"));
      document.body.dataset.firstRenderCity = document.documentElement.dataset.city || "";
      document.body.dataset.firstRenderTitle = title?.textContent?.trim() || "";
      document.body.dataset.firstRenderHeaderVisible = header && getComputedStyle(header).display !== "none" ? "true" : "false";
      document.body.dataset.firstRenderHeaderHeight = header ? String(Math.round(header.getBoundingClientRect().height)) : "0";
      document.body.dataset.firstRenderBottomVisible = bottom && getComputedStyle(bottom).display !== "none" ? "true" : "false";
      document.body.dataset.firstRenderHeroHidden = hero && getComputedStyle(hero).display === "none" ? "true" : "false";
      document.body.dataset.firstRenderArtReady = art && getComputedStyle(art).backgroundImage !== "none" ? "true" : "false";
      document.body.dataset.firstRenderMobileCss = mobileSheet ? "true" : "false";
      document.body.dataset.firstRenderNoOverflow = document.documentElement.scrollWidth <= document.documentElement.clientWidth ? "true" : "false";
    })();
  </script>'''
    source = source.replace("</body>", diagnostic + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def dump_dom(city: str, url: str, width: int, height: int) -> str:
    with tempfile.TemporaryDirectory(prefix=f"vivamos-first-{city}-", ignore_cleanup_errors=True) as profile:
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
            f"--window-size={width},{height}",
            "--virtual-time-budget=1200",
            f"--user-data-dir={profile}",
            "--dump-dom",
            url,
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=30)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome first-render probe failed: {result.stderr[-1200:]}")
        return result.stdout


def run_case(city: str, label: str, base_url: str, width: int, height: int) -> None:
    make_test_page(city)
    dom = dump_dom(city, f"{base_url}/app/__first_render_test.html", width, height)
    expected = {
        f'data-first-render-city="{city}"': "saved city was not applied before paint",
        f'data-first-render-title="{label}"': "city title was not ready before module JavaScript",
        'data-first-render-header-visible="true"': "header is hidden on first render",
        'data-first-render-bottom-visible="true"': "header controls are missing on first render",
        'data-first-render-hero-hidden="true"': "retired hero flashes before header redesign",
        'data-first-render-art-ready="true"': "city artwork is missing on first render",
        'data-first-render-mobile-css="true"': "mobile CSS was not loaded from head",
        'data-first-render-no-overflow="true"': "first render creates horizontal overflow",
    }
    for marker, message in expected.items():
        if marker not in dom:
            raise AssertionError(f"{message}: {city} at {width}x{height}")

    match = re.search(r'data-first-render-header-height="(\d+)"', dom)
    if not match or int(match.group(1)) < 150:
        raise AssertionError(f"header collapsed on first render: {city} at {width}x{height}")
    print(f"First render {city} {width}x{height}: stable")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            base_url = f"http://127.0.0.1:{port}"
            for city, label in (("valparaiso", "Valparaíso / Viña del Mar"), ("gijon", "Gijón / Xixón")):
                run_case(city, label, base_url, 1280, 900)
                run_case(city, label, base_url, 390, 844)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
