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


def make_test_page() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    source = source.replace("<body>", '<body>\n<script>localStorage.setItem("agenda-cultural-city", "valparaiso"); localStorage.removeItem("agenda-cultural-favorites-v1");</script>', 1)
    probe = r'''<script>(async()=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));let b=null;for(let i=0;i<30;i++){b=document.querySelector('.event-card[data-event-id] > [data-favorite-toggle]');if(b)break;await sleep(300)}if(!b){document.body.dataset.favoritesProbe='missing-toggle';return}const id=b.closest('.event-card[data-event-id]')?.dataset.eventId||'';b.click();await sleep(700);let stored=[];try{stored=JSON.parse(localStorage.getItem('agenda-cultural-favorites-v1')||'[]')}catch{}const saved=stored.some(x=>x.city==='valparaiso'&&x.id===id);const pressed=b.getAttribute('aria-pressed')==='true';const count=document.querySelector('[data-favorites-access] [data-favorites-count]')?.textContent?.trim()||'';document.body.dataset.favoritesEventId=id;document.body.dataset.favoritesProbe=saved&&pressed&&count==='1'&&!document.querySelector('[data-my-plans]')?'pass':'fail'})();</script>'''
    source = source.replace("</body>", probe + "\n</body>", 1)
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
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=42)
    if result.returncode != 0 or not result.stdout:
        raise AssertionError(f"Favorites browser probe failed: exit={result.returncode}; stderr={result.stderr[-1200:]}")
    return result.stdout


def run_scenario(port: int) -> None:
    with tempfile.TemporaryDirectory(prefix="agenda-favorites-browser-", ignore_cleanup_errors=True) as profile:
        home = run_chrome(f"http://127.0.0.1:{port}/app/__favorites_test.html", profile, 12000)
        if 'data-favorites-probe="pass"' not in home:
            raise AssertionError("Favorites compact-home contract failed")
        match = re.search(r'data-favorites-event-id="([^"]+)"', home)
        if not match:
            raise AssertionError("Favorites test did not capture a saved event id")
        plans = run_chrome(f"http://127.0.0.1:{port}/app/mis-planes.html?city=valparaiso", profile, 8000)
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
                    print("Favorites browser test: homepage stays compact and standalone Mis planes renders saved activities")
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
