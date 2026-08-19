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
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
SAFE_PAGE = APP / "__startup_safe_mode_test.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def dump_dom(url: str, label: str, virtual_time_ms: int = 10000) -> str:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-startup-{label}-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(),
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication",
                "--metrics-recording-only",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1280,900",
                f"--virtual-time-budget={virtual_time_ms}",
                f"--user-data-dir={profile}",
                "--dump-dom",
                url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=40)
            except subprocess.TimeoutExpired as exc:
                last_error = f"timeout after {exc.timeout}s"
                if attempt < 2:
                    time.sleep(1)
                    continue
                raise AssertionError(f"Chrome startup probe timed out twice ({label}): {last_error}") from exc
            if result.returncode == 0 and result.stdout:
                return result.stdout
            last_error = result.stderr[-1600:] or f"exit={result.returncode}, empty DOM"
            if attempt < 2:
                time.sleep(1)
    raise AssertionError(f"Chrome startup probe failed twice ({label}): {last_error}")


def assert_ready_dom(dom: str, city: str, *, safe_mode: bool) -> None:
    if 'data-vivamos-ready="true"' not in dom:
        raise AssertionError(f"startup never reached ready state for {city}")
    if f'data-city="{city}"' not in dom:
        raise AssertionError(f"startup did not activate city {city}")
    if dom.count('class="event-card') <= 0:
        raise AssertionError(f"startup rendered no event cards for {city}")

    if safe_mode:
        if 'data-vivamos-safe-mode="active"' not in dom:
            raise AssertionError("watchdog did not activate independent safe mode")
        if "Modo seguro" not in dom:
            raise AssertionError("safe-mode agenda did not expose its recovery state")
    elif 'data-vivamos-safe-mode="active"' in dom:
        raise AssertionError(f"normal startup unexpectedly fell back to safe mode for {city}")

    status_match = re.search(r'<section class="status"([^>]*)>(.*?)</section>', dom, flags=re.S)
    if status_match:
        attrs, body = status_match.groups()
        visible = "hidden" not in attrs
        if visible and "Preparando la agenda" in re.sub(r"<[^>]+>", "", body):
            raise AssertionError(f"startup remained visibly frozen for {city}")


def make_safe_mode_page() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    source = re.sub(r'\s*<script type="module" src="[^"]+"></script>', "", source)
    modules = '''
  <script type="module" src="./startup-stability.js?v=20260819-startup2"></script>
  <script type="module" src="./pwa.js"></script>
'''
    source = source.replace("</body>", modules + "</body>", 1)
    SAFE_PAGE.write_text(source, encoding="utf-8")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        base = f"http://127.0.0.1:{port}/app"
        try:
            for city in ("valparaiso", "gijon"):
                url = f"{base}/?city={city}&startup={uuid.uuid4().hex}"
                dom = dump_dom(url, f"normal-{city}", virtual_time_ms=10000)
                assert_ready_dom(dom, city, safe_mode=False)
                print(f"STARTUP_NORMAL_OK city={city}")

            make_safe_mode_page()
            url = f"{base}/{SAFE_PAGE.name}?city=valparaiso&startup={uuid.uuid4().hex}"
            dom = dump_dom(url, "safe-valparaiso", virtual_time_ms=9000)
            assert_ready_dom(dom, "valparaiso", safe_mode=True)
            print("STARTUP_SAFE_MODE_OK city=valparaiso")
        finally:
            SAFE_PAGE.unlink(missing_ok=True)
            server.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
