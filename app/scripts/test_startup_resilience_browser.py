from __future__ import annotations

import http.server
import os
import queue
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.parse
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
NORMAL_PAGE = APP / "__startup_normal_test.html"
SAFE_PAGE = APP / "__startup_safe_mode_test.html"
PROBES: queue.Queue[dict[str, str]] = queue.Queue()


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class ProbeHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/__startup_probe":
            values = {key: items[-1] for key, items in urllib.parse.parse_qs(parsed.query).items() if items}
            PROBES.put(values)
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()


PROBE_SCRIPT = r'''
  <script>
    (() => {
      let sent = false;
      const send = (mode) => {
        if (sent) return;
        sent = true;
        requestAnimationFrame(() => setTimeout(() => {
          const status = document.querySelector("[data-status]");
          const params = new URLSearchParams({
            token: new URLSearchParams(location.search).get("probe") || "",
            mode,
            ready: document.documentElement.dataset.vivamosReady || "",
            safe: document.documentElement.dataset.vivamosSafeMode || "",
            city: document.documentElement.dataset.city || "",
            cards: String(document.querySelectorAll(".event-card").length),
            status_hidden: status?.hidden ? "true" : "false",
            status_text: String(status?.textContent || "").replace(/\s+/g, " ").trim().slice(0, 160),
          });
          fetch(`/__startup_probe?${params}`, { cache: "no-store", keepalive: true }).catch(() => {});
        }, 0));
      };
      window.addEventListener("vivamos:core-ready", (event) => send(event?.detail?.mode || "core"), { once: true });
      if (document.documentElement.dataset.vivamosReady === "true") send("already-ready");
      window.addEventListener("error", (event) => {
        if (!sent) console.error("startup probe page error", event.error || event.message);
      });
      window.addEventListener("unhandledrejection", (event) => {
        if (!sent) console.error("startup probe rejection", event.reason);
      });
    })();
  </script>
'''


def inject_probe_before_app(source: str) -> str:
    marker = '  <script type="module" src="./app.js"></script>'
    if marker not in source:
        raise AssertionError("index.html no longer contains the app.js module entrypoint")
    return source.replace(marker, PROBE_SCRIPT + "\n" + marker, 1)


def make_pages() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    NORMAL_PAGE.write_text(inject_probe_before_app(source), encoding="utf-8")

    safe = re.sub(r'\s*<script type="module" src="[^"]+"></script>', "", source)
    safe_modules = '''
  <script type="module" src="./startup-stability.js?v=20260819-startup2"></script>
'''
    safe = safe.replace("</body>", PROBE_SCRIPT + safe_modules + "</body>", 1)
    SAFE_PAGE.write_text(safe, encoding="utf-8")


def chrome_command(url: str, profile: str) -> list[str]:
    return [
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
        f"--user-data-dir={profile}",
        url,
    ]


def wait_for_probe(url: str, token: str, label: str, timeout: float) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix=f"vivamos-startup-{label}-", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen(
            chrome_command(url, profile),
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                remaining = max(0.1, deadline - time.monotonic())
                try:
                    probe = PROBES.get(timeout=min(0.5, remaining))
                except queue.Empty:
                    if process.poll() is not None:
                        raise AssertionError(f"Chrome exited before startup became ready ({label}), exit={process.returncode}")
                    continue
                if probe.get("token") == token:
                    return probe
            raise AssertionError(f"No startup-ready beacon within {timeout:.0f}s ({label})")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=4)


def assert_probe(probe: dict[str, str], city: str, *, safe_mode: bool) -> None:
    if probe.get("ready") != "true":
        raise AssertionError(f"startup did not set READY for {city}: {probe}")
    if probe.get("city") != city:
        raise AssertionError(f"startup did not activate {city}: {probe}")
    if int(probe.get("cards", "0") or 0) <= 0:
        raise AssertionError(f"startup rendered no event cards for {city}: {probe}")
    if probe.get("status_hidden") != "true" and "Preparando la agenda" in probe.get("status_text", ""):
        raise AssertionError(f"startup remained visibly frozen for {city}: {probe}")

    if safe_mode:
        if probe.get("safe") != "active" or probe.get("mode") != "safe":
            raise AssertionError(f"watchdog did not activate independent safe mode: {probe}")
    elif probe.get("safe") == "active" or probe.get("mode") == "safe":
        raise AssertionError(f"normal startup unexpectedly used safe mode for {city}: {probe}")


def run_probe(base: str, page: str, city: str, label: str, *, safe_mode: bool, timeout: float) -> None:
    token = uuid.uuid4().hex
    url = f"{base}/{page}?city={city}&probe={token}"
    probe = wait_for_probe(url, token, label, timeout)
    assert_probe(probe, city, safe_mode=safe_mode)
    print(f"STARTUP_{'SAFE_MODE' if safe_mode else 'NORMAL'}_OK city={city} cards={probe.get('cards')}")


def main() -> None:
    os.chdir(ROOT)
    while not PROBES.empty():
        PROBES.get_nowait()
    make_pages()
    handler = lambda *args, **kwargs: ProbeHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        base = f"http://127.0.0.1:{port}/app"
        try:
            run_probe(base, NORMAL_PAGE.name, "valparaiso", "normal-valparaiso", safe_mode=False, timeout=15)
            run_probe(base, NORMAL_PAGE.name, "gijon", "normal-gijon", safe_mode=False, timeout=15)
            run_probe(base, SAFE_PAGE.name, "valparaiso", "safe-valparaiso", safe_mode=True, timeout=12)
        finally:
            NORMAL_PAGE.unlink(missing_ok=True)
            SAFE_PAGE.unlink(missing_ok=True)
            server.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
