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
TEST_PAGE = APP / "__pwa_critical_features_test.html"


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
window.__criticalPwaErrors = [];
window.addEventListener("error", (event) => {
  window.__criticalPwaErrors.push(`error:${event.message || "unknown"}:${event.filename || ""}:${event.lineno || 0}`);
});
window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason;
  window.__criticalPwaErrors.push(`rejection:${reason?.stack || reason?.message || String(reason)}`);
});
</script>
'''

PROBE = r'''
<script>
setTimeout(() => {
  const body = document.body;
  const cards = [...document.querySelectorAll('.event-card[data-event-id]')];
  const enhanced = cards.filter((card) => card.dataset.cardEnhanced === 'true');
  const media = cards.filter((card) => card.querySelector('.event-card-media'));
  const images = cards.filter((card) => card.querySelector('.event-card-media img'));
  const favorites = document.querySelector('[data-favorites-access]');
  const mobileNav = document.querySelector('[data-mobile-tabbar]');
  const topCity = document.querySelector('[data-city-switch]');
  const chooser = document.querySelector('[data-chooser-backdrop]');

  body.dataset.criticalCards = String(cards.length);
  body.dataset.criticalEnhanced = String(enhanced.length);
  body.dataset.criticalMedia = String(media.length);
  body.dataset.criticalImages = String(images.length);
  body.dataset.criticalFavorites = String(Boolean(favorites));
  body.dataset.criticalMobileNav = String(Boolean(mobileNav));
  body.dataset.criticalErrors = (window.__criticalPwaErrors || []).join(' || ');

  topCity?.click();
  setTimeout(() => {
    body.dataset.criticalTopCity = String(Boolean(chooser && !chooser.hidden));
    if (chooser) chooser.hidden = true;
    const mobileCity = document.querySelector('[data-mobile-action="city"]');
    mobileCity?.click();
    setTimeout(() => {
      body.dataset.criticalMobileCity = String(Boolean(!mobileCity || (chooser && !chooser.hidden)));
      body.dataset.criticalDone = 'true';
    }, 200);
  }, 200);
}, 5200);
</script>
'''


def make_test_page(city: str) -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    source = source.replace("</head>", ERROR_TRAP + "\n</head>", 1)
    bootstrap = f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>\n'
    source = source.replace(
        '<script type="module" src="./app.js"></script>',
        bootstrap + '<script type="module" src="./app.js"></script>',
        1,
    )
    source = source.replace("</body>", PROBE + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def dump_dom(city: str, url: str) -> str:
    with tempfile.TemporaryDirectory(prefix=f"agenda-critical-pwa-{city}-", ignore_cleanup_errors=True) as profile:
        cmd = [
            chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-background-networking", "--disable-extensions",
            "--disable-sync", "--no-first-run", "--no-default-browser-check",
            "--disable-features=ServiceWorker,PushMessaging,BackgroundSync",
            "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
            "--window-size=390,844", "--virtual-time-budget=7000",
            f"--user-data-dir={profile}", "--dump-dom", url,
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=25)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome failed for {city}: exit={result.returncode}; stderr={result.stderr[-1200:]}")
        return result.stdout


def value(dom: str, name: str) -> str:
    match = re.search(fr'data-{name}="([^"]*)"', dom)
    return match.group(1) if match else "<missing>"


def run_city(city: str, base_url: str) -> None:
    make_test_page(city)
    dom = dump_dom(city, f"{base_url}/app/__pwa_critical_features_test.html?city={city}")
    cards = int(value(dom, "critical-cards"))
    enhanced = int(value(dom, "critical-enhanced"))
    media = int(value(dom, "critical-media"))
    images = int(value(dom, "critical-images"))
    assert value(dom, "critical-done") == "true", f"{city}: critical PWA probe did not finish"
    assert cards > 0, f"{city}: no event cards rendered"
    assert enhanced == cards, f"{city}: only {enhanced}/{cards} cards were enriched"
    assert media == cards, f"{city}: only {media}/{cards} cards have media"
    assert images == cards, f"{city}: only {images}/{cards} cards have an image or category fallback"
    assert value(dom, "critical-favorites") == "true", f"{city}: Mis planes access is missing"
    assert value(dom, "critical-mobile-nav") == "true", f"{city}: mobile navigation is missing"
    assert value(dom, "critical-top-city") == "true", f"{city}: header city selector does not open"
    assert value(dom, "critical-mobile-city") == "true", f"{city}: mobile city selector does not open"
    assert value(dom, "critical-errors") == "", f"{city}: uncaught browser errors: {value(dom, 'critical-errors')}"
    print(f"Critical PWA {city}: {cards}/{cards} cards enriched with images; Mis planes and both city controls work")


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
