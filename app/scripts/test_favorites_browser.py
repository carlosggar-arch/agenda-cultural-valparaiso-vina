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


def make_test_page() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    source = source.replace(
        "<body>",
        '<body>\n<script>localStorage.setItem("agenda-cultural-city", "valparaiso"); localStorage.removeItem("agenda-cultural-favorites-v1");</script>',
        1,
    )
    probe = r'''
<script>
(() => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const run = async () => {
    let button = null;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      button = document.querySelector('.event-card[data-event-id] > [data-favorite-toggle]');
      if (button) break;
      await sleep(300);
    }
    if (!button) {
      document.body.dataset.favoritesProbe = 'missing-toggle';
      return;
    }
    const card = button.closest('.event-card[data-event-id]');
    const id = card?.dataset.eventId || '';
    button.click();
    await sleep(700);
    let stored = [];
    try { stored = JSON.parse(localStorage.getItem('agenda-cultural-favorites-v1') || '[]'); } catch {}
    const saved = stored.some((item) => item.city === 'valparaiso' && item.id === id);
    const row = document.querySelector(`[data-my-plans] .my-plan-row[data-event-id="${CSS.escape(id)}"]`);
    const disclosure = document.querySelector('[data-my-plans] .my-plans-disclosure');
    const pressed = button.getAttribute('aria-pressed') === 'true';
    const count = document.querySelector('[data-my-plans] .my-plans-count')?.textContent?.trim() || '';
    const compactInitially = Boolean(disclosure) && !disclosure.open;
    document.querySelector('[data-mobile-action="plans"]')?.click();
    await sleep(200);
    const openedByPlansTab = Boolean(disclosure?.open);
    document.body.dataset.favoritesSaved = String(saved);
    document.body.dataset.favoritesInPlans = String(Boolean(row));
    document.body.dataset.favoritesPressed = String(pressed);
    document.body.dataset.favoritesCount = count;
    document.body.dataset.favoritesCompactInitially = String(compactInitially);
    document.body.dataset.favoritesOpenedByTab = String(openedByPlansTab);
    document.body.dataset.favoritesProbe = saved && row && pressed && count.startsWith('1 ') && compactInitially && openedByPlansTab ? 'pass' : 'fail';
  };
  run();
})();
</script>
'''
    source = source.replace("</body>", probe + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); time.sleep(0.2)
        with tempfile.TemporaryDirectory(prefix="agenda-favorites-browser-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking", "--disable-extensions",
                "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
                "--virtual-time-budget=14000", f"--user-data-dir={profile}", "--dump-dom",
                f"http://127.0.0.1:{port}/app/__favorites_test.html",
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=45)
            finally:
                server.shutdown(); thread.join(timeout=2); TEST_PAGE.unlink(missing_ok=True)

    if result.returncode != 0 or not result.stdout:
        raise AssertionError(f"Favorites browser probe failed: exit={result.returncode}; stderr={result.stderr[-1200:]}")
    if 'data-favorites-probe="pass"' not in result.stdout:
        observed = ", ".join(re.findall(r'data-favorites-[a-z-]+="[^"]*"', result.stdout)[-12:])
        raise AssertionError(f"Favorites compact browser contract failed; observed: {observed or 'no probe attributes'}")
    print("Favorites browser test: Mis planes stays compact and opens from the mobile tab")


if __name__ == "__main__":
    main()
