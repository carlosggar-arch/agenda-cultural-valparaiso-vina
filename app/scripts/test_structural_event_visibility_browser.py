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
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
DATASET = ROOT / "agenda_web.json"
TEST_PAGE = APP / "__structural_visibility_test.html"

THEATRE_ID = "agenda_111111111111111111111111"
PCDV_IDS = ("agenda_222222222222222222222222", "agenda_333333333333333333333333")
ESTADIO_IDS = (
    "agenda_444444444444444444444444",
    "agenda_555555555555555555555555",
    "agenda_666666666666666666666666",
)
EXPECTED_IDS = (THEATRE_ID, *PCDV_IDS, *ESTADIO_IDS)


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


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


def make_test_page() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    expected_js = json.dumps(list(EXPECTED_IDS))
    pcdv_js = json.dumps(list(PCDV_IDS))
    estadio_js = json.dumps(list(ESTADIO_IDS))
    diagnostic = f'''
  <script>
    (() => {{
      const expected = {expected_js};
      const pcdv = {pcdv_js};
      const estadio = {estadio_js};
      const visible = (node) => {{
        if (!node || node.hidden || node.closest('[hidden]')) return false;
        const style = getComputedStyle(node);
        return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
      }};
      const represented = (id) => {{
        const direct = [...document.querySelectorAll('[data-event-id]')]
          .some((node) => node.dataset.eventId === id && visible(node));
        const row = [...document.querySelectorAll('[data-grouped-event-id]')]
          .some((node) => node.dataset.groupedEventId === id && visible(node));
        return direct || row;
      }};
      const probe = () => {{
        const missing = expected.filter((id) => !represented(id));
        const group = [...document.querySelectorAll('[data-unified-exhibition-group="true"]')]
          .find((node) => pcdv.every((id) => String(node.dataset.eventGroup || '').split(',').includes(id)) && visible(node));
        const teatroVisible = represented({json.dumps(THEATRE_ID)});
        const estadioVisible = estadio.filter(represented).length;
        const pcdvVisible = pcdv.filter(represented).length;
        document.body.dataset.structuralVisibilityExpected = String(expected.length);
        document.body.dataset.structuralVisibilityVisible = String(expected.length - missing.length);
        document.body.dataset.structuralVisibilityMissing = missing.join(',');
        document.body.dataset.structuralVisibilityPcdv = String(pcdvVisible);
        document.body.dataset.structuralVisibilityPcdvGroup = group ? 'true' : 'false';
        document.body.dataset.structuralVisibilityTheatre = teatroVisible ? 'true' : 'false';
        document.body.dataset.structuralVisibilityEstadio = String(estadioVisible);
      }};
      for (const name of ['vivamos:agenda-rendered', 'vivamos:exhibition-groups-rendered', 'vivamos:core-ready']) {{
        window.addEventListener(name, () => setTimeout(probe, 120));
      }}
      setTimeout(probe, 3500);
    }})();
  </script>'''
    source = source.replace("</body>", diagnostic + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def dump_dom(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="vivamos-visibility-", ignore_cleanup_errors=True) as profile:
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
            "--window-size=1280,1000",
            "--virtual-time-budget=5500",
            f"--user-data-dir={profile}",
            "--dump-dom",
            url,
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome structural visibility probe failed: {result.stderr[-1600:]}")
        return result.stdout


def diagnostic_values(dom: str) -> dict[str, str]:
    names = (
        "expected", "visible", "missing", "pcdv", "pcdv-group", "theatre", "estadio",
    )
    values: dict[str, str] = {}
    for name in names:
        match = re.search(rf'data-structural-visibility-{re.escape(name)}="([^"]*)"', dom)
        values[name] = match.group(1) if match else "(absent)"
    return values


def main() -> None:
    original_text = DATASET.read_text(encoding="utf-8")
    original = json.loads(original_text)
    os.chdir(ROOT)
    try:
        DATASET.write_text(json.dumps(fixture_payload(original), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        make_test_page()
        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            time.sleep(0.2)
            try:
                dom = dump_dom(f"http://127.0.0.1:{port}/app/__structural_visibility_test.html?city=valparaiso")
            finally:
                server.shutdown()
                thread.join(timeout=2)

        diagnostics = diagnostic_values(dom)
        print("STRUCTURAL_VISIBILITY_DIAGNOSTICS " + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
        expected_markers = {
            'data-structural-visibility-expected="6"': "fixture count was not evaluated",
            'data-structural-visibility-visible="6"': "one or more approved fixture events disappeared from the rendered agenda",
            'data-structural-visibility-missing=""': "approved fixture IDs are missing from the visible DOM",
            'data-structural-visibility-pcdv="2"': "one or more Parque Cultural exhibitions were lost or hidden",
            'data-structural-visibility-pcdv-group="true"': "Parque Cultural exhibitions were visible but did not survive the grouping renderer as one accessible group",
            'data-structural-visibility-theatre="true"': "theatre event was lost or hidden",
            'data-structural-visibility-estadio="3"': "one or more Estadio Español events were lost or hidden",
        }
        for marker, message in expected_markers.items():
            if marker not in dom:
                raise AssertionError(message + f"; diagnostics={diagnostics}; expected marker {marker}")
        print("Structural event visibility browser contract: OK (theatre + Parque Cultural grouped exhibitions + Estadio Español)")
    finally:
        DATASET.write_text(original_text, encoding="utf-8")
        TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
