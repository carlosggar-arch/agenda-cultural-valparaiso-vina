from __future__ import annotations

import argparse
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
import unicodedata
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


def fold(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(text.lower().split())


def exhibition_like(event: dict) -> bool:
    ids = {str((event.get("primary_category") or {}).get("id") or "").strip().lower()}
    ids.update(
        str(category.get("id") or "").strip().lower()
        for category in event.get("categories") or []
        if isinstance(category, dict)
    )
    return bool(ids & {"exposiciones", "museos"})


def dataset_for(city: str) -> dict:
    path = APP / "data/gijon/agenda_web.json" if city == "gijon" else ROOT / "agenda_web.json"
    return json.loads(path.read_text(encoding="utf-8"))


def real_venue_events(city: str, target: str) -> list[dict]:
    needle = fold(target)
    selected = []
    for event in dataset_for(city).get("events") or []:
        venue = (event.get("location") or {}).get("venue")
        if needle not in fold(venue) or not exhibition_like(event):
            continue
        copy = json.loads(json.dumps(event, ensure_ascii=False))
        copy["image"] = {}
        selected.append(copy)
    if len(selected) < 2:
        raise AssertionError(f"{city}: fewer than two exhibition records for {target}")
    return selected


def make_test_page(city: str, expected_label: str, target: str) -> None:
    events = real_venue_events(city, target)
    payload = html.escape(json.dumps(events, ensure_ascii=False), quote=False)
    city_json = json.dumps(city, ensure_ascii=False)
    target_json = json.dumps(target, ensure_ascii=False)
    label_json = json.dumps(expected_label, ensure_ascii=False)

    source = f'''<!doctype html>
<html lang="es" data-city="{html.escape(city)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Exhibition visual parity</title>
  <link rel="stylesheet" href="./app.css">
  <link id="unified-exhibition-gallery-styles" rel="stylesheet" href="./exhibition-gallery.css?v=20260818-gallery2">
  <link id="unified-exhibition-compact-styles" rel="stylesheet" href="./exhibition-compact.css?v=20260818-compact8">
  <style>
    html, body {{ margin:0; min-height:100%; background:#f6f3ec; }}
    body {{ font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    #visual-capture-root {{ box-sizing:border-box; display:flex; justify-content:center; align-items:flex-start; min-height:100vh; padding:18px; background:#f6f3ec; }}
    #visual-capture-root .event-grid {{ display:block !important; width:430px !important; max-width:calc(100vw - 36px) !important; margin:0 !important; }}
    #visual-capture-root .exhibition-venue-card {{ display:flex !important; width:100% !important; margin:0 !important; }}
    #visual-parity-status {{ display:none !important; }}
  </style>
</head>
<body>
  <main><div class="event-grid" data-dated-grid></div></main>
  <script id="fixture-data" type="application/json">{payload}</script>
  <script type="module">
    import {{ publishAgendaRuntimeSnapshot }} from "./agenda-runtime-state.mjs?v=20260819-runtime1";
    import {{ normalizeVenueAliases }} from "./venue-identity.mjs";

    const cityId = {city_json};
    const targetNeedle = {target_json};
    const expectedLabel = {label_json};
    const fold = (value) => String(value || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase().replace(/\\s+/g, " ").trim();
    const events = normalizeVenueAliases(JSON.parse(document.getElementById("fixture-data").textContent));
    const grid = document.querySelector("[data-dated-grid]");

    // Feed the canonical renderer a real core-group anchor. This intentionally
    // avoids coupling visual parity to the current overlap/date window: temporal
    // grouping already has dedicated CI, while this probe verifies that both
    // cities use the same component, DOM structure and no-clipping geometry.
    const anchor = document.createElement("article");
    anchor.className = "event-card event-card--dated";
    anchor.dataset.eventGroup = events.map((event) => String(event.id || "")).filter(Boolean).join(",");
    anchor.dataset.category = "exposiciones";
    grid.append(anchor);

    publishAgendaRuntimeSnapshot({{ id: cityId }}, {{ dataset: {{ events }}, secondaryPrograms: [], hiddenPrograms: [], diagnostics: [] }});

    function structureSignature(card) {{
      const keep = new Set(["exhibition-collage","exhibition-venue-body","exhibition-venue-meta","exhibition-venue-heading","exhibition-venue-facts","exhibition-group-details","exhibition-group-list","grouped-exhibition-item","grouped-exhibition-media","grouped-exhibition-copy","grouped-exhibition-actions"]);
      const pick = (node) => node ? [...node.classList].filter((name) => keep.has(name)).join(".") : "missing";
      const body = card.querySelector(".exhibition-venue-body");
      const details = card.querySelector(".exhibition-group-details");
      const row = card.querySelector(".grouped-exhibition-item");
      return [pick(card.firstElementChild), pick(body), ...(body ? [...body.children].map(pick) : []), ...(details ? [...details.children].map(pick) : []), ...(row ? [...row.children].map(pick) : [])].join(">");
    }}

    function captureTarget() {{
      const rootHtml = document.documentElement;
      if (rootHtml.dataset.visualParityReady === "true") return true;
      const compact = document.getElementById("unified-exhibition-compact-styles");
      const gallery = document.getElementById("unified-exhibition-gallery-styles");
      if (!compact?.sheet || !gallery?.sheet) return false;
      const card = [...document.querySelectorAll('.exhibition-venue-card[data-unified-exhibition-group="true"]')]
        .find((candidate) => fold(candidate.querySelector("h4")?.textContent).includes(fold(targetNeedle)));
      if (!card) return false;

      const required = [".exhibition-collage",".exhibition-venue-body",".exhibition-venue-meta",".exhibition-venue-heading",".exhibition-venue-facts",".exhibition-group-details",".exhibition-group-list"];
      const missing = required.filter((selector) => !card.querySelector(selector));
      const rows = [...card.querySelectorAll(".grouped-exhibition-item")];
      const clipped = rows.filter((row) => row.scrollHeight > row.clientHeight + 1);

      const status = document.createElement("output");
      status.id = "visual-parity-status";
      status.dataset.targetVenue = card.querySelector("h4")?.textContent?.trim() || expectedLabel;
      status.dataset.targetEvents = String(events.length);
      status.dataset.rowCount = String(rows.length);
      status.dataset.missingParts = missing.length ? missing.join(",") : "none";
      status.dataset.clippedRows = String(clipped.length);
      status.dataset.renderer = card.dataset.unifiedExhibitionGroup === "true" ? "unified" : "other";
      status.dataset.structureSignature = structureSignature(card);

      const captureRoot = document.createElement("div");
      captureRoot.id = "visual-capture-root";
      const captureGrid = document.createElement("div");
      captureGrid.className = "event-grid";
      const clone = card.cloneNode(true);
      clone.hidden = false;
      clone.dataset.visualTarget = "true";
      const details = clone.querySelector(".exhibition-group-details");
      if (details) details.open = true;
      const list = clone.querySelector(".exhibition-group-list");
      if (list) list.scrollTop = 0;
      captureGrid.append(clone);
      captureRoot.append(captureGrid);
      document.body.replaceChildren(status, captureRoot);
      rootHtml.dataset.visualParityReady = "true";
      return true;
    }}

    window.addEventListener("vivamos:exhibition-groups-rendered", () => setTimeout(captureTarget, 60));
    await import("./exhibition-groups.js?v=20260820-groups1");
    for (const delay of [60, 140, 260, 500, 900, 1400]) setTimeout(captureTarget, delay);
  </script>
</body>
</html>'''
    TEST_PAGE.write_text(source, encoding="utf-8")


def chrome_command(profile: str, url: str) -> list[str]:
    return [
        chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
        "--disable-background-networking", "--disable-component-update", "--disable-default-apps", "--disable-extensions",
        "--disable-sync", "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication", "--metrics-recording-only",
        "--no-first-run", "--no-default-browser-check", "--window-size=720,980", "--virtual-time-budget=2800",
        f"--user-data-dir={profile}", url,
    ]


def dump_dom(city: str, url: str) -> str:
    last_error = ""
    for attempt in range(2):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-exhibition-dom-{city}-", ignore_cleanup_errors=True) as profile:
            cmd = chrome_command(profile, url)
            cmd.insert(-1, "--dump-dom")
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=18)
            except subprocess.TimeoutExpired as exc:
                last_error = f"timeout after {exc.timeout}s"
                if attempt == 0:
                    continue
                raise AssertionError(f"Chrome visual DOM probe timed out twice for {city}: {last_error}") from exc
            if result.returncode == 0 and result.stdout:
                return result.stdout
            last_error = result.stderr[-1400:] or f"exit={result.returncode}, empty DOM"
    raise AssertionError(f"Chrome visual DOM probe failed for {city}: {last_error}")


def write_static_capture(dom: str) -> None:
    CAPTURE_PAGE.write_text(re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", dom, flags=re.I), encoding="utf-8")


def screenshot(city: str, url: str, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=f"vivamos-exhibition-shot-{city}-", ignore_cleanup_errors=True) as profile:
        cmd = chrome_command(profile, url)
        cmd.insert(-1, "--run-all-compositor-stages-before-draw")
        cmd.insert(-1, f"--screenshot={output}")
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=18)
        if result.returncode != 0 or not output.exists() or output.stat().st_size < 1000:
            raise AssertionError(f"Chrome screenshot failed for {city}: {result.stderr[-1400:]}")


def status_tag(dom: str) -> str | None:
    match = re.search(r'<output(?=[^>]*\bid="visual-parity-status")[^>]*>', dom, flags=re.I)
    return match.group(0) if match else None


def attr(tag: str, name: str) -> str | None:
    match = re.search(rf'\b{re.escape(name)}="([^"]*)"', tag, flags=re.I)
    return html.unescape(match.group(1)) if match else None


def run_case(city: str, expected_label: str, target: str, filename: str, base_url: str, output_dir: Path) -> dict[str, str]:
    make_test_page(city, expected_label, target)
    dom = dump_dom(city, f"{base_url}/app/{TEST_PAGE.name}?city={city}&visual-parity=1")
    if 'data-visual-parity-ready="true"' not in dom:
        raise AssertionError(f"grouped venue not rendered for visual check: {expected_label} ({city})")
    status = status_tag(dom)
    if status is None:
        raise AssertionError(f"visual parity status was not serialized for {expected_label}")
    if attr(status, "data-renderer") != "unified":
        raise AssertionError(f"target venue is not owned by the unified renderer: {expected_label}")
    if attr(status, "data-missing-parts") != "none":
        raise AssertionError(f"shared card structure is incomplete for {expected_label}: {attr(status, 'data-missing-parts') or 'unknown'}")
    if attr(status, "data-clipped-rows") != "0":
        raise AssertionError(f"grouped exhibition subcards are vertically clipped for {expected_label}: {attr(status, 'data-clipped-rows') or 'unknown'}")
    rows = attr(status, "data-row-count")
    if not rows or int(rows) < 2:
        raise AssertionError(f"expected a grouped venue with at least two exhibitions: {expected_label}")

    write_static_capture(dom)
    output = output_dir / filename
    screenshot(city, f"{base_url}/app/{CAPTURE_PAGE.name}?capture={city}", output)
    venue = attr(status, "data-target-venue") or expected_label
    print(f"EXHIBITION_VISUAL_OK city={city} venue={venue} target_events={attr(status, 'data-target-events')} rows={rows} screenshot={output}")
    return {"city": city, "venue": venue, "signature": attr(status, "data-structure-signature") or "", "screenshot": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="/tmp/exhibition-visual-parity")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    os.chdir(ROOT)
    handler = lambda *handler_args, **handler_kwargs: QuietHandler(*handler_args, directory=str(ROOT), **handler_kwargs)
    results = []
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            base_url = f"http://127.0.0.1:{port}"
            for case in CASES:
                results.append(run_case(*case, base_url, output_dir))
        finally:
            TEST_PAGE.unlink(missing_ok=True)
            CAPTURE_PAGE.unlink(missing_ok=True)
            server.shutdown()
            thread.join(timeout=2)

    signatures = {result["signature"] for result in results}
    if len(signatures) != 1 or not next(iter(signatures), ""):
        detail = " | ".join(f'{result["city"]}: {result["signature"]}' for result in results)
        raise AssertionError(f"Gijón and Viña do not share the same exhibition card structure: {detail}")
    print("EXHIBITION_VISUAL_PARITY_OK shared_structure=true clipped_rows=0")


if __name__ == "__main__":
    main()
