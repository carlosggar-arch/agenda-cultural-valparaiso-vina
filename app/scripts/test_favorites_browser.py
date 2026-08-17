from __future__ import annotations

import http.server
import json
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
TEST_PAGE = APP / "__mis_planes_test.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def favorite_fixture() -> tuple[str, str]:
    payload = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))
    for event in payload.get("events", []):
        event_id = str(event.get("id") or "").strip()
        title = str(event.get("title") or "").strip()
        if event_id and title:
            favorite = [{
                "city": "valparaiso",
                "id": event_id,
                "title": title,
                "url": None,
                "savedAt": "2026-08-17T12:00:00.000Z",
            }]
            return event_id, json.dumps(favorite, ensure_ascii=False)
    raise AssertionError("Valparaiso dataset has no usable event for Mis planes browser test")


def make_test_page() -> str:
    event_id, favorite_json = favorite_fixture()
    source = (APP / "mis-planes.html").read_text(encoding="utf-8")
    marker = '<script type="module">'
    if marker not in source:
        raise AssertionError("Mis planes module marker not found")
    bootstrap = (
        '<script>'
        'localStorage.setItem("agenda-cultural-city","valparaiso");'
        f'localStorage.setItem("agenda-cultural-favorites-v1",{json.dumps(favorite_json)});'
        '</script>'
    )
    TEST_PAGE.write_text(source.replace(marker, bootstrap + marker, 1), encoding="utf-8")
    return event_id


def dump_dom(url: str) -> str:
    errors: list[str] = []
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"agenda-mis-planes-{attempt}-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(),
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-extensions",
                "--disable-sync",
                "--no-first-run",
                "--no-default-browser-check",
                "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
                "--virtual-time-budget=7000",
                f"--user-data-dir={profile}",
                "--dump-dom",
                url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired:
                errors.append(f"attempt {attempt}: Chrome timed out")
                continue
            if result.returncode == 0 and result.stdout:
                return result.stdout
            errors.append(f"attempt {attempt}: exit={result.returncode}; stderr={result.stderr[-1200:]}")
    raise AssertionError("Mis planes browser probe failed: " + " | ".join(errors))


def main() -> None:
    os.chdir(ROOT)
    event_id = make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with ThreadingServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            dom = dump_dom(f"http://127.0.0.1:{port}/app/__mis_planes_test.html?city=valparaiso")
            if 'data-my-plans="true"' not in dom:
                raise AssertionError("Real Mis planes UI did not render its saved-plans section")
            if f'data-event-id="{event_id}"' not in dom:
                raise AssertionError("Real Mis planes UI did not render the seeded dataset activity")
            if "1 guardado" not in dom:
                raise AssertionError("Real Mis planes UI did not report the saved count")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)
    print("Favorites browser test: the real standalone Mis planes page renders a seeded saved activity")


if __name__ == "__main__":
    main()
