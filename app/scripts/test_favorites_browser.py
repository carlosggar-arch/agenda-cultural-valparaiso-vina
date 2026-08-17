from __future__ import annotations

import html
import http.server
import json
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
TEST_PAGE = APP / "__favorites_test.html"


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


def first_valparaiso_event() -> tuple[str, str]:
    payload = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))
    for event in payload.get("events", []):
        event_id = str(event.get("id") or "").strip()
        title = str(event.get("title") or "").strip()
        if event_id and title:
            return event_id, title
    raise AssertionError("Valparaiso dataset has no usable event for favorites browser test")


def make_test_page() -> None:
    event_id, title = first_valparaiso_event()
    probe = r'''<script>(async()=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));let b=null;for(let i=0;i<30;i++){b=document.querySelector('.event-card[data-event-id] > [data-favorite-toggle]');if(b)break;await sleep(200)}if(!b){document.body.dataset.favoritesProbe='missing-toggle';return}const id=b.closest('.event-card[data-event-id]')?.dataset.eventId||'';b.click();await sleep(500);let stored=[];try{stored=JSON.parse(localStorage.getItem('agenda-cultural-favorites-v1')||'[]')}catch{}const saved=stored.some(x=>x.city==='valparaiso'&&x.id===id);const pressed=b.getAttribute('aria-pressed')==='true';const count=document.querySelector('[data-favorites-access] [data-favorites-count]')?.textContent?.trim()||'';document.body.dataset.favoritesEventId=id;document.body.dataset.favoritesProbe=saved&&pressed&&count==='1'?'pass':'fail'})();</script>'''
    source = f'''<!doctype html>
<html lang="es" data-city="valparaiso">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Favorites probe</title></head>
<body>
<script>localStorage.setItem("agenda-cultural-city","valparaiso");localStorage.removeItem("agenda-cultural-favorites-v1");</script>
<header><div class="header-actions"></div></header>
<main><article class="event-card" data-event-id="{html.escape(event_id, quote=True)}"><h3>{html.escape(title)}</h3></article></main>
<script type="module" src="./favorites.js"></script>
{probe}
</body>
</html>'''
    TEST_PAGE.write_text(source, encoding="utf-8")


def run_chrome(url: str, profile: str, budget: int) -> str:
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
        f"--virtual-time-budget={budget}",
        f"--user-data-dir={profile}",
        "--dump-dom",
        url,
    ]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=30)
    if result.returncode != 0 or not result.stdout:
        raise AssertionError(f"Favorites browser probe failed: exit={result.returncode}; stderr={result.stderr[-1200:]}")
    return result.stdout


def run_scenario(port: int) -> None:
    with tempfile.TemporaryDirectory(prefix="agenda-favorites-browser-", ignore_cleanup_errors=True) as profile:
        fixture = run_chrome(f"http://127.0.0.1:{port}/app/__favorites_test.html", profile, 6500)
        if 'data-favorites-probe="pass"' not in fixture:
            raise AssertionError("Favorites storage/button contract failed")
        match = re.search(r'data-favorites-event-id="([^"]+)"', fixture)
        if not match:
            raise AssertionError("Favorites test did not capture a saved event id")
        plans = run_chrome(f"http://127.0.0.1:{port}/app/mis-planes.html?city=valparaiso", profile, 6500)
        if 'data-my-plans="true"' not in plans or f'data-event-id="{match.group(1)}"' not in plans:
            raise AssertionError("Standalone Mis planes page did not render the saved activity")


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with ThreadingServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        errors: list[str] = []
        try:
            for attempt in range(1, 3):
                try:
                    run_scenario(port)
                    print("Favorites browser test: storage persists into the real standalone Mis planes page")
                    return
                except (AssertionError, subprocess.TimeoutExpired) as exc:
                    errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                    time.sleep(1)
            raise AssertionError("Favorites browser scenario failed after two isolated attempts: " + " | ".join(errors))
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
