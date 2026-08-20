from __future__ import annotations

import argparse
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
TEST_PAGE = APP / "__exhibition_visual_parity.html"
CAPTURE_PAGE = APP / "__exhibition_visual_capture.html"

CASES = (
    ("gijon", "Muséu del Pueblu d'Asturies", "museu del pueblu d'asturies", "gijon-museu-pueblu.png"),
    ("valparaiso", "Museo Palacio Rioja", "palacio rioja", "vina-palacio-rioja.png"),
)


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def make_test_page(city: str, target: str) -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    release_marker = '<script src="./release-version.js"></script>'
    if release_marker not in source:
        raise AssertionError("release-version.js must load before visual-parity bootstrap")

    preload = f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>'
    source = source.replace(release_marker, release_marker + "\n  " + preload, 1)

    style = r'''
  <style>
    html[data-visual-parity-ready="true"] body > *:not(#visual-capture-root) { display:none !important; }
    #visual-capture-root {
      box-sizing:border-box;
      display:flex;
      justify-content:center;
      align-items:flex-start;
      min-height:100vh;
      padding:18px;
      background:#f6f3ec;
    }
    #visual-capture-root .event-grid {
      display:block !important;
      width:430px !important;
      max-width:calc(100vw - 36px) !important;
      margin:0 !important;
    }
    #visual-capture-root .exhibition-venue-card {
      display:flex !important;
      width:100% !important;
      margin:0 !important;
    }
    #visual-parity-status { display:none !important; }
  </style>'''

    diagnostic = f'''
  <script>
    (() => {{
      const targetNeedle = {target!r};
      const fold = (value) => String(value || "")
        .normalize("NFD")
        .replace(/[\\u0300-\\u036f]/g, "")
        .toLowerCase()
        .replace(/\\s+/g, " ")
        .trim();

      function captureTarget() {{
        const html = document.documentElement;
        if (html.dataset.visualParityReady === "true") return true;
        const cards = [...document.querySelectorAll('.exhibition-venue-card[data-unified-exhibition-group="true"]')];
        const card = cards.find((candidate) => fold(candidate.querySelector("h4")?.textContent).includes(fold(targetNeedle)));
        if (!card) return false;

        const required = [
          ".exhibition-collage",
          ".exhibition-venue-body",
          ".exhibition-venue-meta",
          ".exhibition-venue-heading",
          ".exhibition-venue-facts",
          ".exhibition-group-details",
          ".exhibition-group-list",
        ];
        const missing = required.filter((selector) => !card.querySelector(selector));
        const rows = [...card.querySelectorAll(".grouped-exhibition-item")];
        const clipped = rows.filter((row) => row.scrollHeight > row.clientHeight + 1);

        const root = document.createElement("div");
        root.id = "visual-capture-root";
        const status = document.createElement("output");
        status.id = "visual-parity-status";
        status.dataset.targetVenue = card.querySelector("h4")?.textContent?.trim() || "";
        status.dataset.rowCount = String(rows.length);
        status.dataset.missingParts = missing.length ? missing.join(",") : "none";
        status.dataset.clippedRows = String(clipped.length);
        status.dataset.renderer = card.dataset.unifiedExhibitionGroup === "true" ? "unified" : "other";
        root.append(status);

        const grid = document.createElement("div");
        grid.className = "event-grid";
        const clone = card.cloneNode(true);
        clone.hidden = false;
        clone.dataset.visualTarget = "true";
        const details = clone.querySelector(".exhibition-group-details");
        if (details) details.open = true;
        const list = clone.querySelector(".exhibition-group-list");
        if (list) list.scrollTop = 0;
        grid.append(clone);
        root.append(grid);
        document.body.append(root);
        html.dataset.visualParityReady = "true";
        return true;
      }}

      window.addEventListener("vivamos:exhibition-groups-rendered", () => setTimeout(captureTarget, 120));
      for (const delay of [700, 1600, 3200, 5600]) setTimeout(captureTarget, delay);
    }})();
  </script>'''

    source = source.replace("</head>", style + "\n</head>", 1)
    source = source.replace("</body>", diagnostic + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def chrome_command(profile: str, url: str, width: int = 720, height: int = 980) -> list[str]:
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
        f"--window-size={width},{height}",
        "--virtual-time-budget=8000",
        f"--user-data-dir={profile}",
        url,
    ]


def dump_dom(city: str, url: str) -> str:
    with tempfile.TemporaryDirectory(prefix=f"vivamos-exhibition-dom-{city}-", ignore_cleanup_errors=True) as profile:
        cmd = chrome_command(profile, url)
        cmd.insert(-1, "--dump-dom")
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome visual DOM probe failed for {city}: {result.stderr[-1400:]}")
        return result.stdout


def write_static_capture(dom: str) -> None:
    # The first browser process has already isolated the exact rendered card.
    # Persist that serialized DOM without executable scripts; the screenshot
    # process then captures the same state instead of racing the app startup again.
    static_dom = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", dom, flags=re.I)
    CAPTURE_PAGE.write_text(static_dom, encoding="utf-8")


def screenshot(city: str, url: str, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=f"vivamos-exhibition-shot-{city}-", ignore_cleanup_errors=True) as profile:
        cmd = chrome_command(profile, url)
        cmd.insert(-1, "--run-all-compositor-stages-before-draw")
        cmd.insert(-1, f"--screenshot={output}")
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
        if result.returncode != 0 or not output.exists() or output.stat().st_size < 1000:
            raise AssertionError(f"Chrome screenshot failed for {city}: {result.stderr[-1400:]}")


def status_tag(dom: str) -> str | None:
    match = re.search(r'<output(?=[^>]*\bid="visual-parity-status")[^>]*>', dom, flags=re.I)
    return match.group(0) if match else None


def attr(tag: str, name: str) -> str | None:
    match = re.search(rf'\b{re.escape(name)}="([^"]*)"', tag, flags=re.I)
    return match.group(1) if match else None


def run_case(city: str, expected_label: str, target: str, filename: str, base_url: str, output_dir: Path) -> None:
    make_test_page(city, target)
    url = f"{base_url}/app/{TEST_PAGE.name}?city={city}&visual-parity=1"
    dom = dump_dom(city, url)

    if 'data-visual-parity-ready="true"' not in dom:
        raise AssertionError(f"grouped venue not rendered for visual check: {expected_label} ({city})")

    status = status_tag(dom)
    if status is None:
        raise AssertionError(f"visual parity status was not serialized for {expected_label}")

    write_static_capture(dom)
    output = output_dir / filename
    screenshot(city, f"{base_url}/app/{CAPTURE_PAGE.name}?capture={city}", output)

    if attr(status, "data-renderer") != "unified":
        raise AssertionError(f"target venue is not owned by the unified renderer: {expected_label}")
    missing = attr(status, "data-missing-parts")
    if missing != "none":
        raise AssertionError(f"shared card structure is incomplete for {expected_label}: {missing or 'unknown'}")
    clipped = attr(status, "data-clipped-rows")
    if clipped != "0":
        raise AssertionError(f"grouped exhibition subcards are vertically clipped for {expected_label}: {clipped or 'unknown'}")
    rows = attr(status, "data-row-count")
    if not rows or int(rows) < 2:
        raise AssertionError(f"expected a grouped venue with at least two exhibitions: {expected_label}")

    venue = attr(status, "data-target-venue") or expected_label
    print(f"EXHIBITION_VISUAL_OK city={city} venue={venue} rows={rows} screenshot={output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="/tmp/exhibition-visual-parity")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    os.chdir(ROOT)
    handler = lambda *handler_args, **handler_kwargs: QuietHandler(*handler_args, directory=str(ROOT), **handler_kwargs)
    errors: list[str] = []
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            base_url = f"http://127.0.0.1:{port}"
            for case in CASES:
                try:
                    run_case(*case, base_url, output_dir)
                except AssertionError as exc:
                    errors.append(str(exc))
        finally:
            TEST_PAGE.unlink(missing_ok=True)
            CAPTURE_PAGE.unlink(missing_ok=True)
            server.shutdown()
            thread.join(timeout=2)

    if errors:
        raise AssertionError(" | ".join(errors))


if __name__ == "__main__":
    main()
