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
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__date_filter_test.html"
STALE_EVENT_ID = "agenda_93e4dbf4da87420c93c629c6"
DATASET = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))
GROUPED_CINEMA_ID: dict[str, str] = {}


def controlled_reference_instant(dataset: dict) -> str:
    """Return the dataset's own effective instant for historical browser checks."""
    generated_at = str(dataset.get("generated_at") or "").strip()
    if generated_at:
        return generated_at
    publication_date = str(dataset.get("publication_date") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_date):
        return f"{publication_date}T12:00:00-04:00"
    raise AssertionError("date-filter dataset has no controlled reference instant")


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
    reference_instant = json.dumps(controlled_reference_instant(DATASET))
    isolated_boot = rf'''
  <script>
    (() => {{
      const fixed = new Date({reference_instant}).getTime();
      const RealDate = Date;
      class FixedDate extends RealDate {{
        constructor(...args) {{ super(...(args.length ? args : [fixed])); }}
        static now() {{ return fixed; }}
      }}
      FixedDate.parse = RealDate.parse;
      FixedDate.UTC = RealDate.UTC;
      Object.setPrototypeOf(FixedDate, RealDate);
      globalThis.Date = FixedDate;
      document.documentElement.dataset.dateFilterReferenceNow = new RealDate(fixed).toISOString();
    }})();
  </script>
  <script type="module">
    const {{ coreReady }} = await import("./app-core.js?v=20260819-core1");
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


def event_dates(event: dict) -> set[str]:
    schedule = event.get("schedule") or {}
    dates: set[str] = set()
    start = str(schedule.get("start") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", start):
        dates.add(start)
    for occurrence in schedule.get("occurrences") or []:
        if not isinstance(occurrence, dict):
            continue
        value = str(occurrence.get("start") or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            dates.add(value)
    return dates


def recurring_cinema_candidates() -> dict[str, str]:
    candidates: dict[str, list[str]] = {}
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
        occurrences = (event.get("schedule") or {}).get("occurrences") or []
        if len(occurrences) < 2 or not event.get("id"):
            continue
        for selected in event_dates(event):
            candidates.setdefault(selected, []).append(str(event["id"]))
    return {selected: sorted(ids)[0] for selected, ids in candidates.items()}


def selected_test_dates() -> list[str]:
    """Choose dates from the checked-in dataset instead of fossilised calendar days.

    Prefer dates that exercise a multi-occurrence cinema card, then fill with
    dates that contain at least two events. This keeps the browser test tied to
    the date-filter contract while allowing the live cultural programme to roll
    forward without turning CI red simply because a particular film ended.
    """
    publication_date = str(DATASET.get("publication_date") or "")[:10]
    recurring = recurring_cinema_candidates()
    counts: Counter[str] = Counter()
    for event in DATASET.get("events", []):
        for selected in event_dates(event):
            if not publication_date or selected >= publication_date:
                counts[selected] += 1

    selected: list[str] = []
    for date in sorted(recurring):
        if publication_date and date < publication_date:
            continue
        selected.append(date)
        if len(selected) == 2:
            return selected

    for date, count in sorted(counts.items()):
        if count < 2 or date in selected:
            continue
        selected.append(date)
        if len(selected) == 2:
            return selected

    for date in sorted(counts):
        if date not in selected:
            selected.append(date)
        if len(selected) == 2:
            return selected

    if not selected:
        raise AssertionError("current dataset has no dated events for date-filter browser coverage")
    return selected


def recurring_cinema_id_for_date(selected: str) -> str | None:
    if selected in GROUPED_CINEMA_ID:
        return GROUPED_CINEMA_ID[selected]
    event_id = recurring_cinema_candidates().get(selected)
    if event_id:
        GROUPED_CINEMA_ID[selected] = event_id
    return event_id


def assert_selected_date(dom: str, selected: str) -> None:
    if 'data-vivamos-ready="true"' not in dom:
        raise AssertionError(f"core did not reach ready state for {selected}")
    if 'data-date-filter-test-ready="true"' not in dom:
        raise AssertionError(f"combined filters did not finish for {selected}")
    if 'data-date-filter-reference-now=' not in dom:
        raise AssertionError(f"controlled date-filter clock was not installed for {selected}")
    stale = maybe_card_tag(dom, STALE_EVENT_ID)
    if stale is not None and not is_hidden(stale):
        raise AssertionError(f"stale event is visible while filtering {selected}")
    if visible_direct_cards(dom) < 1:
        raise AssertionError(f"date {selected} produced no visible event cards")


def assert_grouped_cinema(dom: str, selected: str) -> None:
    event_id = recurring_cinema_id_for_date(selected)
    if not event_id:
        return
    if is_hidden(card_tag(dom, event_id)):
        raise AssertionError(f"grouped cinema card disappeared for its occurrence on {selected}: {event_id}")


def main() -> None:
    os.chdir(ROOT)
    selected_dates = selected_test_dates()
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            base = f"http://127.0.0.1:{port}/app/{TEST_PAGE.name}"
            for selected in selected_dates:
                nonce = uuid.uuid4().hex
                url = f"{base}?city=valparaiso&when=personalizado&from={selected}&to={selected}&datefilter={nonce}"
                dom = dump_dom(url, selected)
                assert_selected_date(dom, selected)
                assert_grouped_cinema(dom, selected)
                print(
                    f"DATE_FILTER_OK date={selected} visible={visible_direct_cards(dom)} "
                    f"recurring_cinema={bool(recurring_cinema_id_for_date(selected))}"
                )
        finally:
            TEST_PAGE.unlink(missing_ok=True)
            server.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
