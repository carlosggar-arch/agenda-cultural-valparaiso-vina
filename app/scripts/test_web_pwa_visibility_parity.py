from __future__ import annotations

import argparse
import contextlib
import json
import socket
import tempfile
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
PRODUCTION_ORIGINS = {
    "github-pages": "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/app/",
    "cloudflare": "https://vivamos.pages.dev/app/",
}
STATES = ("hoy", "7-dias", "todos")
READY_TIMEOUT = 25


def city_ids() -> list[str]:
    payload = json.loads((APP / "cities.json").read_text(encoding="utf-8"))
    return [str(city.get("id") or "").strip() for city in payload.get("cities", []) if city.get("id")]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        return


@contextlib.contextmanager
def local_origin():
    port = free_port()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/app/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def chrome_options(profile: str) -> Options:
    options = Options()
    options.page_load_strategy = "eager"
    for argument in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication",
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=390,844",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(argument)
    return options


def freeze_clock(driver: webdriver.Chrome, instant: str) -> None:
    script = r"""
    (() => {
      const fixed = new Date(%s).getTime();
      const RealDate = Date;
      class FixedDate extends RealDate {
        constructor(...args) { super(...(args.length ? args : [fixed])); }
        static now() { return fixed; }
      }
      Object.setPrototypeOf(FixedDate, RealDate);
      globalThis.Date = FixedDate;
    })();
    """ % json.dumps(instant)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})


def wait_ready(driver: webdriver.Chrome, city: str) -> None:
    WebDriverWait(driver, READY_TIMEOUT, poll_frequency=0.05).until(
        lambda current: current.execute_script(
            """
            return document.documentElement.dataset.vivamosReady === 'true'
              && document.documentElement.dataset.city === arguments[0]
              && document.querySelectorAll('.event-card').length > 0;
            """,
            city,
        )
    )


def wait_service_worker(driver: webdriver.Chrome) -> None:
    driver.set_script_timeout(READY_TIMEOUT)
    ready = driver.execute_async_script(
        """
        const done = arguments[arguments.length - 1];
        if (!navigator.serviceWorker) { done({ok:false, reason:'unsupported'}); return; }
        navigator.serviceWorker.ready.then(async (registration) => {
          const names = globalThis.caches ? await caches.keys() : [];
          done({ok:Boolean(registration.active), cacheCount:names.length});
        }).catch((error) => done({ok:false, reason:String(error)}));
        """
    )
    if not ready or not ready.get("ok") or int(ready.get("cacheCount", 0)) <= 0:
        raise AssertionError(f"PWA cache not ready: {ready}")


def set_state(driver: webdriver.Chrome, state: str) -> None:
    selector = f'[data-combined-when] [data-filter-value="{state}"]'
    buttons = driver.find_elements(By.CSS_SELECTOR, selector)
    if not buttons:
        raise AssertionError(f"Missing canonical combined date filter: {state}")
    driver.execute_script("arguments[0].click()", buttons[0])
    WebDriverWait(driver, 8, poll_frequency=0.05).until(
        lambda current: current.find_element(By.CSS_SELECTOR, selector).get_attribute("aria-pressed") == "true"
    )


def visible_records(driver: webdriver.Chrome, state: str) -> tuple[tuple[str, str, str, str], ...]:
    values = driver.execute_script(
        """
        const output = [];
        const visible = (node) => node && !node.hidden && getComputedStyle(node).display !== 'none';
        for (const card of document.querySelectorAll('.event-card')) {
          if (!visible(card)) continue;
          const grouped = String(card.dataset.eventGroup || '').split(',').map((x) => x.trim()).filter(Boolean);
          const append = (id, owner = card) => output.push({
            id,
            category: String(owner.dataset.category || card.dataset.category || ''),
            temporal: String(owner.dataset.temporalBucket || card.dataset.temporalBucket || ''),
            section: arguments[0],
          });
          if (grouped.length) {
            const rows = [...card.querySelectorAll('[data-grouped-event-id]')];
            if (rows.length) {
              for (const row of rows) if (visible(row) && row.dataset.groupedEventId) append(row.dataset.groupedEventId, row);
            } else {
              for (const id of grouped) append(id);
            }
          } else if (card.dataset.eventId) {
            append(card.dataset.eventId);
          }
        }
        return output.filter((record, index) => output.findIndex((candidate) => candidate.id === record.id) === index);
        """,
        state,
    )
    return tuple(
        (
            str(value.get("id") or ""),
            str(value.get("category") or ""),
            str(value.get("temporal") or ""),
            str(value.get("section") or ""),
        )
        for value in values or []
    )


def wait_presentation_metadata(driver: webdriver.Chrome) -> None:
    WebDriverWait(driver, 8, poll_frequency=0.05).until(
        lambda current: current.execute_script(
            """
            const visible = (node) => node && !node.hidden && getComputedStyle(node).display !== 'none';
            const cards = [...document.querySelectorAll('.event-card')].filter(visible);
            return cards.length > 0 && cards.every((card) => card.dataset.category && card.dataset.temporalBucket);
            """
        )
    )


def capture_states(driver: webdriver.Chrome) -> dict[str, tuple[tuple[str, str, str, str], ...]]:
    captured: dict[str, tuple[tuple[str, str, str, str], ...]] = {}
    for state in STATES:
        set_state(driver, state)
        wait_presentation_metadata(driver)
        records = visible_records(driver, state)
        if state == "todos" and not records:
            raise AssertionError("Canonical 'todos' state rendered zero visible event IDs")
        captured[state] = records
    return captured


def set_offline(driver: webdriver.Chrome, offline: bool) -> None:
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.emulateNetworkConditions",
        {
            "offline": offline,
            "latency": 0,
            "downloadThroughput": -1,
            "uploadThroughput": -1,
            "connectionType": "none" if offline else "wifi",
        },
    )


def compare_snapshots(
    origin: str,
    city: str,
    instant: str,
    online: dict[str, tuple[tuple[str, str, str, str], ...]],
    pwa: dict[str, tuple[tuple[str, str, str, str], ...]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for state in STATES:
        web_records = online[state]
        pwa_records = pwa[state]
        web_ids = {record[0] for record in web_records}
        pwa_ids = {record[0] for record in pwa_records}
        if web_records != pwa_records:
            missing = sorted(web_ids - pwa_ids)
            extra = sorted(pwa_ids - web_ids)
            raise AssertionError(
                "WEB_PWA_PRESENTATION_MISMATCH "
                f"origin={origin} city={city} state={state} at={instant} "
                f"web={len(web_records)} pwa={len(pwa_records)} missing={missing} extra={extra} "
                f"web_records={web_records} pwa_records={pwa_records}"
            )
        exact_ids = [record[0] for record in web_records]
        rows.append(
            {
                "origin": origin,
                "city": city,
                "state": state,
                "at": instant,
                "count": len(exact_ids),
                "ids": exact_ids,
                "presentation": [
                    {"id": record[0], "category": record[1], "temporal": record[2], "section": record[3]}
                    for record in web_records
                ],
            }
        )
        print(
            "WEB_PWA_PRESENTATION_PARITY_OK "
            f"origin={origin} city={city} state={state} at={instant} records={len(exact_ids)}"
        )
    return rows


def exercise_origin(name: str, base: str, instant: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for city in city_ids():
        with tempfile.TemporaryDirectory(prefix=f"vivamos-parity-{name}-{city}-") as profile:
            driver = webdriver.Chrome(options=chrome_options(profile))
            try:
                freeze_clock(driver, instant)
                set_offline(driver, False)
                driver.get(f"{base}?city={city}&parity=online")
                wait_ready(driver, city)
                online = capture_states(driver)
                wait_service_worker(driver)
                driver.get("about:blank")
                set_offline(driver, True)
                driver.get(f"{base}?city={city}&parity=pwa")
                wait_ready(driver, city)
                pwa = capture_states(driver)
                rows.extend(compare_snapshots(name, city, instant, online, pwa))
            finally:
                try:
                    set_offline(driver, False)
                except Exception:
                    pass
                driver.quit()
    return rows


def normalized_instant(value: str | None) -> str:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def write_report(path: str, mode: str, instant: str, rows: list[dict[str, object]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "mode": mode,
        "at": instant,
        "rows": rows,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WEB_PWA_VISIBILITY_REPORT_OK path={output} rows={len(rows)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Require exact visible event-ID parity between live web and cached PWA.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--production", action="store_true")
    mode.add_argument("--local", action="store_true")
    parser.add_argument("--at", default=None, help="Offset-aware ISO instant; defaults to current UTC minute.")
    parser.add_argument("--json-output", default=None, help="Optional JSON evidence output with the exact visible IDs.")
    args = parser.parse_args()
    instant = normalized_instant(args.at)
    rows: list[dict[str, object]] = []

    if args.production:
        report_mode = "production"
        for name, base in PRODUCTION_ORIGINS.items():
            rows.extend(exercise_origin(name, base, instant))
    else:
        report_mode = "local"
        with local_origin() as base:
            rows.extend(exercise_origin("local", base, instant))

    if args.json_output:
        write_report(args.json_output, report_mode, instant, rows)
    print(f"WEB_PWA_VISIBILITY_PARITY_COMPLETE at={instant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
