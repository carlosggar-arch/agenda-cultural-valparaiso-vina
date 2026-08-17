from __future__ import annotations

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
TEST_PAGE = APP / "__full_pwa_runtime_diag.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available")


class QuietHandler(__import__("http.server").server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


ERROR_TRAP = r'''
<script>
window.__fullPwaErrors = [];
window.addEventListener("error", (event) => {
  window.__fullPwaErrors.push(`error:${event.message || "unknown"}:${event.filename || ""}:${event.lineno || 0}`);
});
window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  window.__fullPwaErrors.push(`rejection:${reason?.stack || reason?.message || String(reason)}`);
});
</script>
'''

DIAGNOSTIC = r'''
<script>
setTimeout(() => {
  const body = document.body;
  const cards = [...document.querySelectorAll('.event-card[data-event-id]')];
  const enhanced = cards.filter((card) => card.dataset.cardEnhanced === 'true');
  const media = cards.filter((card) => card.querySelector('.event-card-media'));
  const imgs = cards.filter((card) => card.querySelector('.event-card-media img'));
  const favAccess = document.querySelector('[data-favorites-access]');
  const mobileNav = document.querySelector('[data-mobile-tabbar]');
  const topCity = document.querySelector('[data-city-switch]');
  const chooser = document.querySelector('[data-chooser-backdrop]');

  body.dataset.fullDiagCards = String(cards.length);
  body.dataset.fullDiagEnhanced = String(enhanced.length);
  body.dataset.fullDiagMedia = String(media.length);
  body.dataset.fullDiagImages = String(imgs.length);
  body.dataset.fullDiagFavorites = String(Boolean(favAccess));
  body.dataset.fullDiagMobileNav = String(Boolean(mobileNav));
  body.dataset.fullDiagPwaVersion = document.querySelector('[data-app-version]')?.textContent || '';
  body.dataset.fullDiagErrors = (window.__fullPwaErrors || []).join(' || ');

  topCity?.click();
  setTimeout(() => {
    body.dataset.fullDiagTopCityOpens = String(Boolean(chooser && !chooser.hidden));
    if (chooser) chooser.hidden = true;
    const mobileCity = document.querySelector('[data-mobile-action="city"]');
    mobileCity?.click();
    setTimeout(() => {
      body.dataset.fullDiagMobileCityOpens = String(Boolean(!mobileCity || (chooser && !chooser.hidden)));
      body.dataset.fullDiagDone = 'true';
    }, 200);
  }, 200);
}, 5200);
</script>
'''


def make_test_page(city: str) -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    source = source.replace("</head>", ERROR_TRAP + "\n</head>", 1)
    bootstrap = f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>\n'
    source = source.replace("<script type=\"module\" src=\"./app.js\"></script>", bootstrap + '<script type="module" src="./app.js"></script>', 1)
    source = source.replace("</body>", DIAGNOSTIC + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def dump_dom(city: str, url: str) -> str:
    with tempfile.TemporaryDirectory(prefix=f"agenda-full-pwa-{city}-", ignore_cleanup_errors=True) as profile:
        cmd = [
            chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-background-networking", "--disable-extensions",
            "--disable-sync", "--no-first-run", "--no-default-browser-check",
            "--disable-features=ServiceWorker,PushMessaging,BackgroundSync",
            "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
            "--window-size=390,844", "--virtual-time-budget=7000",
            f"--user-data-dir={profile}", "--dump-dom", url,
        ]
        try:
            result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=25)
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            code = 124
        if stdout and 'data-full-diag-done="true"' in stdout:
            return stdout
        raise AssertionError(f"Chrome failed for {city}: exit={code}; stderr={stderr[-1600:]}; dom_tail={stdout[-1600:]}")


def marker(dom: str, name: str) -> str:
    match = re.search(fr'data-{name}="([^"]*)"', dom)
    return match.group(1) if match else "<missing>"


def run_city(city: str, base_url: str) -> None:
    make_test_page(city)
    dom = dump_dom(city, f"{base_url}/app/__full_pwa_runtime_diag.html?city={city}")
    names = [
        "full-diag-done", "full-diag-cards", "full-diag-enhanced", "full-diag-media",
        "full-diag-images", "full-diag-favorites", "full-diag-mobile-nav", "full-diag-pwa-version",
        "full-diag-top-city-opens", "full-diag-mobile-city-opens", "full-diag-errors",
    ]
    values = {name: marker(dom, name) for name in names}
    print(city, values, flush=True)
    if values["full-diag-done"] != "true":
        raise AssertionError(f"{city}: diagnostic did not complete: {values}")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler) as server:
        server.daemon_threads = True
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); time.sleep(0.2)
        try:
            for city in ("valparaiso", "gijon"):
                run_city(city, f"http://127.0.0.1:{port}")
        finally:
            server.shutdown(); thread.join(timeout=2); TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
