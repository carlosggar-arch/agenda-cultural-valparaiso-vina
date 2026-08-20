from __future__ import annotations

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
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__date_filter_test.html"
STALE_EVENT_ID = "agenda_93e4dbf4da87420c93c629c6"
DATASET = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))


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
    source = re.sub(r'\s*<script type="module" src="[^"]+"></script>', "", source)
    isolated_boot = r'''
  <script type="module">
    const { coreReady } = await import("./app-core.js?v=20260819-core1");
    await coreReady;
    await import("./combined-filters-bootstrap.js?v=20260819-date-test1");
    document.documentElement.dataset.dateFilterTestReady = "true";
  </script>'''
    source = source.replace("</body>", isolated_boot + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def dump_dom(url: str, label: str) -> str:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-date-{label}-", ignore_cleanup_errors=True) as profile:
            cmd = [
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
                "--virtual-time-budget=7000",
                f"--user-data-dir={profile}",
                "--dump-dom",
                url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
            except subprocess.TimeoutExpired as exc:
                last_error = f"timeout after {exc.timeout}s"
                if attempt < 2:
                    time.sleep(1)
                    continue
                raise AssertionError(f"Chrome date-filter probe timed out twice ({label}): {last_error}") from exc
            if result.stdout:
                return result.stdout
            last_error = result.stderr[-1600:] or f"exit={result.returncode}, empty DOM"
            if attempt < 2:
                time.sleep(1)
    raise AssertionError(f"Chrome date-filter probe failed twice ({label}): {last_error}")


def maybe_card_tag(dom: str, event_id: str) -> str | None:
    match = re.search(rf'<article(?=[^>]*\bdata-event-id="{re.escape(event_id)}")[^>]*>', dom, flags=re.I)
    return match.group(0) if match else None


def card_tag(dom: str, event_id: str) -> str:
    tag = maybe_card_tag(dom, event_id)
    if not tag:
        raise AssertionError(f"event card not rendered: {event_id}")
    return tag


def is_hidden(tag: str) -> bool:
    return re.search(r'\shidden(?:\s|=|>)', tag, flags=re.I) is not None


def visible_direct_cards(dom: str) -> int:
    tags = re.findall(r'<article(?=[^>]*\bclass="[^"]*\bevent-card\b)(?=[^>]*\bdata-event-id="[^"]+")[^>]*>', dom, flags=re.I)
    return sum(not is_hidden(tag) for tag in tags)


def recurring_cinema_id_for_date(selected: str) -> str:
    candidates: list[str] = []
    for event in DATASET.get("events", []):
        categories = {
            str(category.get("id") or category.get("label") or "").strip().lower()
            for category in (event.get("categories") or [])
            if isinstance(category, dict)
        }
        primary = event.get("primary_category") or {}
        categories.add(str(primary.get("id") or primary.get("label") or "").strip().lower())
        if not ({"cine", "cinema"} & categories):
            continue

        schedule = event.get("schedule") or {}
        occurrences = schedule.get("occurrences") or []
        occurrence_dates = {
            str(occurrence.get("start") or "")[:10]
            for occurrence in occurrences
            if isinstance(occurrence, dict) and occurrence.get("start")
        }
        if len(occurrences) >= 2 and selected in occurrence_dates and event.get("id"):
            candidates.append(str(event["id"]))

    if not candidates:
        raise AssertionError(f"no current recurring cinema event covers {selected}")
    return sorted(candidates)[0]


def assert_selected_date(dom: str, selected: str) -> None:
    if 'data-vivamos-ready="true"' not in dom:
        raise AssertionError(f"core did not reach ready state for {selected}")
    if 'data-date-filter-test-ready="true"' not in dom:
        raise AssertionError(f"combined filters did not finish for {selected}")
    stale = maybe_card_tag(dom, STALE_EVENT_ID)
    if stale is not None and not is_hidden(stale):
        raise AssertionError(f"yesterday event is visible while filtering {selected}")
    if visible_direct_cards(dom) < 2:
        raise AssertionError(f"date {selected} collapsed to fewer than two visible event cards")


def assert_grouped_cinema(dom: str, selected: str) -> None:
    event_id = recurring_cinema_id_for_date(selected)
    if is_hidden(card_tag(dom, event_id)):
        raise AssertionError(f"grouped cinema card disappeared for its occurrence on {selected}: {event_id}")


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            base = f"http://127.0.0.1:{port}/app/{TEST_PAGE.name}"
            for selected in ("2026-08-20", "2026-08-25"):
                nonce = uuid.uuid4().hex
                url = f"{base}?city=valparaiso&when=personalizado&from={selected}&to={selected}&datefilter={nonce}"
                dom = dump_dom(url, selected)
                assert_selected_date(dom, selected)
                assert_grouped_cinema(dom, selected)
                print(f"DATE_FILTER_OK date={selected} visible={visible_direct_cards(dom)}")
        finally:
            TEST_PAGE.unlink(missing_ok=True)
            server.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
