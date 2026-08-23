from __future__ import annotations

import http.server
import json
import os
import shutil
import socketserver
import tempfile
import threading
import time
from datetime import date, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "agenda_web.json"

THEATRE_ID = "agenda_111111111111111111111111"
PCDV_IDS = ("agenda_222222222222222222222222", "agenda_333333333333333333333333")
ESTADIO_IDS = (
    "agenda_444444444444444444444444",
    "agenda_555555555555555555555555",
    "agenda_666666666666666666666666",
)
EXPECTED_IDS = (THEATRE_ID, *PCDV_IDS, *ESTADIO_IDS)
READY_TIMEOUT_SECONDS = 20
STABILITY_SAMPLES = 3
STABILITY_INTERVAL_SECONDS = 0.2


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


def chrome_options(profile: str) -> Options:
    options = Options()
    options.binary_location = chrome_binary()
    options.page_load_strategy = "eager"
    for argument in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,1000",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(argument)
    return options


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def dated_event(event_id: str, title: str, category: str, label: str, day: date, *, venue: str, city: str, source_name: str, source_url: str) -> dict:
    start = f"{day.isoformat()}T19:00:00-04:00"
    return {
        "id": event_id,
        "title": title,
        "event_type": "event",
        "primary_category": {"id": category, "label": label},
        "categories": [{"id": category, "label": label}],
        "schedule": {"mode": "dated", "start": start, "end": None, "timezone": "America/Santiago", "display_text": f"{day.isoformat()} · 19:00", "occurrences": []},
        "location": {"venue_id": None, "city": city, "commune": city, "venue": venue, "address": None, "online": False, "latitude": None, "longitude": None},
        "price": {"is_free": True, "currency": "CLP", "min_amount": 0, "max_amount": 0, "display_text": "Gratis"},
        "links": {"official": source_url, "tickets": None, "registration": None, "source": source_url},
        "organizer": source_name,
        "source_name": source_name,
        "source_url": source_url,
        "last_verified_at": date.today().isoformat(),
        "public_status": {"source_official": True, "last_verified_at": date.today().isoformat(), "registration_open": None, "registration_closed": None, "cancelled": False, "sold_out": None, "price_stage": None, "price_confirmed": True, "information_completeness": "complete", "advisory_text": None},
        "description": "Fixture estructural de visibilidad. No se publica.",
        "tags": [],
        "audience": None,
        "registration_requirements": None,
        "image": {"url": None, "alt": None},
    }


def exhibition_event(event_id: str, title: str, start_day: date, end_day: date) -> dict:
    event = dated_event(
        event_id,
        title,
        "exposiciones",
        "Exposiciones",
        start_day,
        venue="Parque Cultural de Valparaíso",
        city="Valparaíso",
        source_name="Parque Cultural de Valparaíso",
        source_url=f"https://parquecultural.cl/events/fixture-{event_id[-4:]}/",
    )
    event["schedule"] = {
        "mode": "multi_day",
        "start": start_day.isoformat(),
        "end": end_day.isoformat(),
        "timezone": "America/Santiago",
        "display_text": f"{start_day.isoformat()} – {end_day.isoformat()}",
        "occurrences": [],
    }
    return event


def fixture_payload(original: dict) -> dict:
    today = date.today()
    events = [
        dated_event(
            THEATRE_ID,
            "Obra teatral fixture",
            "teatro",
            "Teatro",
            today + timedelta(days=2),
            venue="Teatro Municipal de Viña del Mar",
            city="Viña del Mar",
            source_name="Teatro Municipal de Viña del Mar",
            source_url="https://teatrovina.cl/evento/fixture-estructural/",
        ),
        exhibition_event(PCDV_IDS[0], "Exposición Parque fixture A", today - timedelta(days=5), today + timedelta(days=25)),
        exhibition_event(PCDV_IDS[1], "Exposición Parque fixture B", today - timedelta(days=3), today + timedelta(days=30)),
        dated_event(
            ESTADIO_IDS[0], "Actividad Estadio fixture A", "ferias-gastronomia", "Ferias y gastronomía", today + timedelta(days=1),
            venue="Estadio Español", city="Viña del Mar", source_name="Estadio Español Recreo", source_url="https://www.instagram.com/p/fixture-a/",
        ),
        dated_event(
            ESTADIO_IDS[1], "Actividad Estadio fixture B", "cine", "Cine", today + timedelta(days=4),
            venue="Estadio Español", city="Viña del Mar", source_name="Estadio Español Recreo", source_url="https://www.instagram.com/p/fixture-b/",
        ),
        dated_event(
            ESTADIO_IDS[2], "Actividad Estadio fixture C", "musica", "Música", today + timedelta(days=7),
            venue="Estadio Español", city="Viña del Mar", source_name="Estadio Español Recreo", source_url="https://www.instagram.com/p/fixture-c/",
        ),
    ]
    return {
        "schema_version": original.get("schema_version", "1.2.0"),
        "generated_at": f"{today.isoformat()}T12:00:00-04:00",
        "publication_date": today.isoformat(),
        "timezone": "America/Santiago",
        "counts": {"total": len(events), "events": len(events), "courses": 0, "flexible_offers": 0, "programs": 0},
        "events": events,
    }


def visibility_snapshot(driver: webdriver.Chrome) -> dict[str, object]:
    return driver.execute_script(
        """
        const expected = arguments[0];
        const pcdv = arguments[1];
        const estadio = arguments[2];
        const theatre = arguments[3];
        const visible = (node) => {
          if (!node || node.hidden || node.closest('[hidden]')) return false;
          const style = getComputedStyle(node);
          return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
        };
        const represented = (id) => {
          const direct = [...document.querySelectorAll('[data-event-id]')]
            .some((node) => node.dataset.eventId === id && visible(node));
          const row = [...document.querySelectorAll('[data-grouped-event-id]')]
            .some((node) => node.dataset.groupedEventId === id && visible(node));
          return direct || row;
        };
        const missing = expected.filter((id) => !represented(id));
        const group = [...document.querySelectorAll('[data-unified-exhibition-group="true"]')]
          .find((node) => pcdv.every((id) => String(node.dataset.eventGroup || '').split(',').includes(id)) && visible(node));
        return {
          ready: document.documentElement.dataset.vivamosReady === 'true',
          expected: expected.length,
          visible: expected.length - missing.length,
          missing,
          pcdv: pcdv.filter(represented).length,
          pcdvGroup: Boolean(group),
          theatre: represented(theatre),
          estadio: estadio.filter(represented).length,
        };
        """,
        list(EXPECTED_IDS),
        list(PCDV_IDS),
        list(ESTADIO_IDS),
        THEATRE_ID,
    )


def fully_visible(snapshot: dict[str, object]) -> bool:
    return bool(
        snapshot.get("ready")
        and snapshot.get("visible") == len(EXPECTED_IDS)
        and not snapshot.get("missing")
        and snapshot.get("pcdv") == len(PCDV_IDS)
        and snapshot.get("theatre") is True
        and snapshot.get("estadio") == len(ESTADIO_IDS)
    )


def wait_for_stable_visibility(driver: webdriver.Chrome) -> dict[str, object]:
    latest: dict[str, object] = {}

    def ready(current: webdriver.Chrome) -> bool:
        nonlocal latest
        latest = visibility_snapshot(current)
        return fully_visible(latest)

    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(ready)
    for _ in range(STABILITY_SAMPLES):
        time.sleep(STABILITY_INTERVAL_SECONDS)
        latest = visibility_snapshot(driver)
        if not fully_visible(latest):
            raise AssertionError(f"Structural visibility became unstable after readiness: {latest}")
    return latest


def main() -> None:
    original_text = DATASET.read_text(encoding="utf-8")
    original = json.loads(original_text)
    os.chdir(ROOT)
    try:
        DATASET.write_text(json.dumps(fixture_payload(original), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            time.sleep(0.2)
            try:
                with tempfile.TemporaryDirectory(prefix="vivamos-visibility-", ignore_cleanup_errors=True) as profile:
                    driver = webdriver.Chrome(options=chrome_options(profile))
                    try:
                        driver.get(f"http://127.0.0.1:{port}/app/index.html?city=valparaiso&structural-visibility=1")
                        diagnostics = wait_for_stable_visibility(driver)
                    finally:
                        driver.quit()
            finally:
                server.shutdown()
                thread.join(timeout=2)

        print("STRUCTURAL_VISIBILITY_DIAGNOSTICS " + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
        if not fully_visible(diagnostics):
            raise AssertionError(f"one or more approved fixture events disappeared from the rendered agenda: {diagnostics}")
        print(
            "Structural event visibility browser contract: OK "
            f"(theatre + Parque Cultural + Estadio Español; grouping={diagnostics['pcdvGroup']}; "
            f"stable_samples={STABILITY_SAMPLES})"
        )
    finally:
        DATASET.write_text(original_text, encoding="utf-8")


if __name__ == "__main__":
    main()
