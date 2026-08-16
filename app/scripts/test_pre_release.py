from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
    assert data[12:16] == b"IHDR", f"{path} missing IHDR"
    return struct.unpack(">II", data[16:24])


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_manifest_and_icons() -> None:
    manifest = load_json(APP / "manifest.webmanifest")
    assert manifest.get("start_url") == "./"
    assert manifest.get("scope") == "./"
    assert manifest.get("display") == "standalone"

    icons = {item["src"]: item for item in manifest.get("icons", [])}
    required = {
        "./icons/icon-192.png": (192, 192, "any"),
        "./icons/icon-512.png": (512, 512, "any"),
        "./icons/icon-maskable-512.png": (512, 512, "maskable"),
    }
    for src, (width, height, purpose) in required.items():
        assert src in icons, f"missing manifest icon: {src}"
        icon_path = APP / src.removeprefix("./")
        assert icon_path.exists(), f"missing icon file: {icon_path}"
        assert png_size(icon_path) == (width, height), f"wrong PNG size for {src}"
        assert purpose in str(icons[src].get("purpose", "")), f"wrong purpose for {src}"


def check_service_worker() -> None:
    sw = (APP / "service-worker.js").read_text(encoding="utf-8")
    assert "networkFirstDataset" in sw
    assert "../agenda_web.json" in sw
    assert "./data/gijon/agenda_web.json" in sw
    assert "DATA_CACHE" in sw
    assert "SHELL_CACHE" in sw

    shell_start = sw.index("const SHELL_ASSETS")
    shell_end = sw.index("];", shell_start)
    shell_block = sw[shell_start:shell_end]
    assert "agenda_web.json" not in shell_block, "city datasets must never be precached"


def check_ui_contract() -> None:
    index = (APP / "index.html").read_text(encoding="utf-8")
    app_js = (APP / "app.js").read_text(encoding="utf-8")
    pwa_js = (APP / "pwa.js").read_text(encoding="utf-8") if (APP / "pwa.js").exists() else ""

    assert './manifest.webmanifest' in index
    assert './icons/icon-192.png' in index
    assert ('./service-worker.js' in app_js) or ('./service-worker.js' in pwa_js)
    assert '../agenda_web.json' in app_js
    assert './data/gijon/agenda_web.json' in app_js
    assert 'event?.event_type === "program"' in app_js
    assert 'event?.event_type === "flexible_offer"' in app_js


def validate_dataset(path: Path, *, expected_city: str | None = None) -> dict:
    data = load_json(path)
    events = data.get("events")
    assert isinstance(events, list), f"events must be a list in {path}"
    ids = [event.get("id") for event in events]
    assert all(ids), f"missing event id in {path}"
    assert len(ids) == len(set(ids)), f"duplicate event ids in {path}"

    for event in events:
        assert event.get("title"), f"missing title in {path}"
        assert isinstance(event.get("schedule"), dict), f"missing schedule in {path}"
        assert isinstance(event.get("location"), dict), f"missing location in {path}"
        if expected_city:
            assert event.get("location", {}).get("city") == expected_city

    return data


def check_gijon_dataset() -> None:
    data = validate_dataset(APP / "data/gijon/agenda_web.json", expected_city="Gijón")
    assert data.get("schema_version") == "1.2.0"
    assert data.get("timezone") == "Europe/Madrid"
    events = data["events"]
    expected_counts = {
        "total": len(events),
        "events": sum(event.get("event_type") == "event" for event in events),
        "courses": sum(event.get("event_type") == "course" for event in events),
        "flexible_offers": sum(event.get("event_type") == "flexible_offer" for event in events),
        "programs": sum(event.get("event_type") == "program" for event in events),
    }
    assert data.get("counts") == expected_counts
    for event in events:
        assert event.get("event_type") in {"event", "course", "program", "flexible_offer"}
        editorial = event.get("editorial") or {}
        assert editorial.get("classification") == event.get("event_type")


def check_valparaiso_dataset_compatibility() -> None:
    data = validate_dataset(ROOT / "agenda_web.json")
    # The multi-city shell must remain capable of rendering the current Chile dataset.
    for event in data["events"]:
        schedule = event.get("schedule") or {}
        assert schedule.get("start") or schedule.get("display_text") or schedule.get("occurrences"), (
            f"event {event.get('id')} has no renderable schedule"
        )


def check_gijon_source_path() -> None:
    legacy = (APP / "scripts/update_gijon.py").read_text(encoding="utf-8")
    adapter = (APP / "scripts/fetch_gijon_xhtml.py").read_text(encoding="utf-8")
    assert "tipo=JSON" not in legacy, "stale Gijon JSON endpoint remains in update_gijon.py"
    assert "tipo=XHTML" in legacy
    assert "tipo=XHTML" in adapter


def check_duplicate_public_writer_retired() -> None:
    duplicate = ROOT / ".github/workflows/update-gijon-preview.yml"
    assert not duplicate.exists(), "duplicate public Gijon writer must remain retired"


def main() -> None:
    check_manifest_and_icons()
    check_service_worker()
    check_ui_contract()
    check_gijon_dataset()
    check_valparaiso_dataset_compatibility()
    check_gijon_source_path()
    check_duplicate_public_writer_retired()
    print("Joint multi-city pre-release contract: OK")


if __name__ == "__main__":
    main()
