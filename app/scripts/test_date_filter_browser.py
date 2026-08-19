from __future__ import annotations

import html
import http.server
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
STALE_EVENT_ID = "agenda_93e4dbf4da87420c93c629c6"
GROUPED_CINEMA_ID = "agenda_cinema_9531c9ead643b3490477"
GROUPED_CINEMA_TITLE = "Adolescencia, Sexo y Muerte en Camp Miasma"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def dump_dom(url: str, label: str) -> str:
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
            "--virtual-time-budget=12000",
            f"--user-data-dir={profile}",
            "--dump-dom",
            url,
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=45)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome date-filter probe failed ({label}): {result.stderr[-1600:]}")
        return result.stdout


def card_tag(dom: str, event_id: str) -> str:
    match = re.search(rf'<article(?=[^>]*\bdata-event-id="{re.escape(event_id)}")[^>]*>', dom, flags=re.I)
    if not match:
        raise AssertionError(f"event card not rendered: {event_id}")
    return match.group(0)


def card_html(dom: str, event_id: str) -> str:
    match = re.search(rf'(<article(?=[^>]*\bdata-event-id="{re.escape(event_id)}")[^>]*>.*?</article>)', dom, flags=re.I | re.S)
    if not match:
        raise AssertionError(f"event card body not rendered: {event_id}")
    return match.group(1)


def is_hidden(tag: str) -> bool:
    return re.search(r'\shidden(?:\s|=|>)', tag, flags=re.I) is not None


def visible_direct_cards(dom: str) -> int:
    tags = re.findall(r'<article(?=[^>]*\bclass="[^"]*\bevent-card\b)(?=[^>]*\bdata-event-id="[^"]+")[^>]*>', dom, flags=re.I)
    return sum(not is_hidden(tag) for tag in tags)


def assert_selected_date(dom: str, selected: str) -> None:
    if 'data-vivamos-ready="true"' not in dom:
        raise AssertionError(f"app did not reach ready state for {selected}")
    if f'value="{selected}"' not in dom:
        raise AssertionError(f"custom date control did not retain {selected}")
    if 'data-normalized-date-filter="active"' not in dom:
        raise AssertionError("normalized date filter guard did not run")
    if not is_hidden(card_tag(dom, STALE_EVENT_ID)):
        raise AssertionError(f"yesterday event is visible while filtering {selected}")
    if visible_direct_cards(dom) < 2:
        raise AssertionError(f"date {selected} collapsed to fewer than two visible event cards")


def assert_grouped_cinema(dom: str, selected: str) -> None:
    tag = card_tag(dom, GROUPED_CINEMA_ID)
    if is_hidden(tag):
        raise AssertionError(f"grouped cinema card disappeared for its occurrence on {selected}")
    body = html.unescape(re.sub(r"<[^>]+>", " ", card_html(dom, GROUPED_CINEMA_ID)))
    body = re.sub(r"\s+", " ", body)
    if GROUPED_CINEMA_TITLE not in body:
        raise AssertionError("grouped cinema title changed unexpectedly")
    if selected == "2026-08-19" and not ("13:00" in body and "18:00" in body):
        raise AssertionError("same-day grouped cinema card does not expose both 13:00 and 18:00 sessions")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            base = f"http://127.0.0.1:{port}/app/"
            for selected in ("2026-08-19", "2026-08-25"):
                nonce = uuid.uuid4().hex
                url = f"{base}?city=valparaiso&when=personalizado&from={selected}&to={selected}&datefilter={nonce}"
                dom = dump_dom(url, selected)
                assert_selected_date(dom, selected)
                assert_grouped_cinema(dom, selected)
                print(f"DATE_FILTER_OK date={selected} visible={visible_direct_cards(dom)}")
        finally:
            server.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
