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
TEST_PAGE = APP / "__temporal_priority_browser_test.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def check_ui_removed() -> None:
    module = (APP / "temporal-priority.js").read_text(encoding="utf-8")
    entry = (APP / "app.js").read_text(encoding="utf-8")

    for removed_marker in (
        "Hoy / No te lo pierdas",
        "Terminan pronto",
        "Próximos eventos puntuales",
        "Exposiciones y muestras vigentes",
        "PRIORITY_BLOCKS",
        "renderPriority",
        "temporalBadge(",
    ):
        assert removed_marker not in module, f"removed temporal UI returned: {removed_marker}"

    assert "shouldSuppressForTemporalFilter" in module, "date-confidence filter guard must remain active"
    assert "removeLegacyTemporalUi" in module, "legacy temporal UI cleanup must remain active"
    assert 'temporal-priority.js?v=20260819-temporal2' in entry, "app entrypoint must load the guard-only temporal module"


def make_page() -> None:
    TEST_PAGE.write_text(
        r'''<!doctype html>
<html><body>
<script type="module">
import { organizeTemporalPriority, temporalBadge } from "./temporal-priority-core.mjs";

const valpo = { timezone: "America/Santiago", locale: "es-CL" };
const gijon = { timezone: "Europe/Madrid", locale: "es-ES" };
const instant = new Date("2026-08-19T00:30:00Z");
const event = (id, start, end, startConfidence, endConfidence, category = "musica") => ({
  id,
  title: id,
  event_type: "event",
  primary_category: { id: category, label: category === "exposiciones" ? "Exposiciones" : "Música" },
  categories: [],
  schedule: { start, end, start_confidence: startConfidence, end_confidence: endConfidence, occurrences: [] },
});

const explicit = event("explicit", "2026-08-19", null, "explicit", null);
const fallback = event("fallback", "2026-08-19", "2026-08-30", "technical_fallback", "explicit", "exposiciones");
const closing = event("closing", "2026-08-01", "2026-08-21", "technical_fallback", "official_revalidation");
const unreliableClose = event("bad-close", "2026-08-01", "2026-08-21", "explicit", "technical_fallback");

const gijonBlocks = organizeTemporalPriority([explicit, fallback, closing, unreliableClose], gijon, instant);
const valpoBlocks = organizeTemporalPriority([explicit, fallback, closing, unreliableClose], valpo, instant);

document.body.dataset.temporalBrowserDone = "true";
document.body.dataset.gijonToday = String(gijonBlocks.today.some((item) => item.id === "explicit"));
document.body.dataset.valpoToday = String(valpoBlocks.today.some((item) => item.id === "explicit"));
document.body.dataset.fallbackToday = String(gijonBlocks.today.some((item) => item.id === "fallback"));
document.body.dataset.reliableClosing = String(gijonBlocks.endingSoon.some((item) => item.id === "closing"));
document.body.dataset.unreliableClosing = String(gijonBlocks.endingSoon.some((item) => item.id === "bad-close"));
document.body.dataset.fallbackBadge = String(temporalBadge(fallback, gijon, instant) || "");
document.body.dataset.closingBadge = String(temporalBadge(closing, gijon, instant) || "");
</script>
</body></html>''',
        encoding="utf-8",
    )


def dump_dom(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="vivamos-temporal-browser-", ignore_cleanup_errors=True) as profile:
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
            "--virtual-time-budget=900",
            f"--user-data-dir={profile}",
            "--dump-dom",
            url,
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=20)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome temporal guard probe failed: {result.stderr[-1200:]}")
        return result.stdout


def main() -> None:
    check_ui_removed()
    os.chdir(ROOT)
    make_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            dom = dump_dom(f"http://127.0.0.1:{port}/app/__temporal_priority_browser_test.html")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)

    expected = {
        'data-temporal-browser-done="true"': "temporal core did not execute in Chrome",
        'data-gijon-today="true"': "Europe/Madrid did not classify the explicit event as today",
        'data-valpo-today="false"': "America/Santiago incorrectly classified the same date as today",
        'data-fallback-today="false"': "technical_fallback created a false Hoy",
        'data-reliable-closing="true"': "reliable ending-soon event was not surfaced by the core",
        'data-unreliable-closing="false"': "unreliable end created ending-soon status",
        'data-fallback-badge=""': "technical fallback generated an affirmative badge in the core",
        'data-closing-badge="Últimos 3 días"': "reliable closing badge core contract changed unexpectedly",
    }
    for marker, message in expected.items():
        if marker not in dom:
            raise AssertionError(message)
    print("Temporal UI removed; Valparaíso/Viña and Gijón confidence guard remains OK")


if __name__ == "__main__":
    main()
