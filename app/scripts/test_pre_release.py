from __future__ import annotations

import json
import struct
import unicodedata
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


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


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
    assert "CITY_REGISTRY_URL" in sw
    assert "datasetUrls" in sw
    assert "../agenda_web.json" in sw
    assert "./data/gijon/agenda_web.json" in sw
    assert "DATA_CACHE" in sw
    assert "SHELL_CACHE" in sw

    shell_start = sw.index("const SHELL_ASSETS")
    shell_end = sw.index("];", shell_start)
    shell_block = sw[shell_start:shell_end]
    assert "agenda_web.json" not in shell_block, "city datasets must never be precached"
    assert '"./cities.json"' in shell_block
    assert '"../assets/city-registry.mjs"' in shell_block
    assert '"./mis-planes.html"' in shell_block
    assert '"../assets/favorites-reminders.mjs"' in shell_block
    assert '"./agenda-runtime-state.mjs"' in shell_block
    assert '"./render-lifecycle.js"' in shell_block


def check_ui_contract() -> None:
    index = (APP / "index.html").read_text(encoding="utf-8")
    app_js = (APP / "app.js").read_text(encoding="utf-8")
    core_js = (APP / "app-core.js").read_text(encoding="utf-8")
    pipeline_js = (APP / "data-pipeline.js").read_text(encoding="utf-8")
    runtime_state = (APP / "agenda-runtime-state.mjs").read_text(encoding="utf-8")
    lifecycle = (APP / "render-lifecycle.js").read_text(encoding="utf-8")
    pwa_js = (APP / "pwa.js").read_text(encoding="utf-8") if (APP / "pwa.js").exists() else ""
    event_detail_js = (APP / "event-detail.js").read_text(encoding="utf-8")
    city_registry = load_json(APP / "cities.json")
    city_registry_js = (ROOT / "assets/city-registry.mjs").read_text(encoding="utf-8")
    reminders = (ROOT / "assets/favorites-reminders.mjs").read_text(encoding="utf-8")

    assert './manifest.webmanifest' in index
    assert './icons/icon-192.png' in index
    assert ('./service-worker.js' in app_js) or ('./service-worker.js' in pwa_js)
    assert 'loadCityRegistry' in core_js
    assert 'const CITIES = CITY_REGISTRY.byId' in core_js
    assert 'loadAgendaDataset(city)' in core_js
    assert 'fetchJson(city.dataset' in pipeline_js
    assert 'publishAgendaRuntimeSnapshot' in pipeline_js
    assert 'vivamos:agenda-data-ready' in runtime_state
    assert 'vivamos:agenda-rendered' in lifecycle
    assert 'subtree: true' not in lifecycle
    assert 'characterData: true' not in lifecycle
    assert 'loadCityRegistry' in city_registry_js
    by_id = {city["id"]: city for city in city_registry.get("cities", [])}
    assert by_id["valparaiso"]["dataset"] == "../agenda_web.json"
    assert by_id["gijon"]["dataset"] == "./data/gijon/agenda_web.json"
    assert 'event?.event_type === "program"' in core_js
    assert 'event?.event_type === "flexible_offer"' in core_js
    assert 'BEGIN:VALARM' in reminders
    assert 'TRIGGER:${option.trigger}' in reminders

    # The permanent URL remains an internal share/SEO primitive, not a user-facing action.
    assert 'function permanentEventUrl(event)' in event_detail_js
    assert 'addButtonAction(actions, "Compartir"' in event_detail_js
    assert 'Ficha permanente →' not in event_detail_js
    assert 'Copiar enlace' not in event_detail_js
    assert 'Fuente de datos ↗' not in event_detail_js
    assert 'else if (registration)' in event_detail_js
    assert 'else if (official)' in event_detail_js


def check_exhibition_layout_guard() -> None:
    compact_js = (APP / "exhibition-compact.js").read_text(encoding="utf-8")
    compact_css = (APP / "exhibition-compact.css").read_text(encoding="utf-8")
    hours_js = (APP / "exhibition-hours.js").read_text(encoding="utf-8")

    # Equal heights must be calculated per visual row. A single tallest card in
    # the whole Gijon dataset must never stretch every card on the page again.
    assert "function visualRows(cards)" in compact_js
    assert "for (const row of visualRows(cards))" in compact_js
    assert "ROW_TOP_TOLERANCE" in compact_js

    # Temporary venue-group anchors are hidden until exhibition-gallery.js has
    # assembled their full content, preventing blank/half-rendered cards.
    assert ".exhibition-group-card[data-event-group]:not(.exhibition-venue-card)" in compact_css
    assert "display: none !important" in compact_css

    # The hours layer may update only a completed group card. Static and runtime
    # renderers share the same hours row and any duplicate is removed.
    group_start = hours_js.index("function patchGroupCard")
    group_end = hours_js.index("function patchCards", group_start)
    group_block = hours_js[group_start:group_end]
    assert 'card.classList.contains("exhibition-venue-card")' in group_block
    assert "setGroupedOpeningHours(card, hours)" in group_block
    assert "upsertOpeningParagraph" not in group_block
    assert 'card.querySelectorAll("[data-exhibition-opening-hours], .exhibition-venue-hours")' in hours_js
    assert "candidates.slice(1)" in hours_js
    assert "duplicate.remove()" in hours_js


def validate_dataset(path: Path) -> dict:
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

    return data


def check_gijon_geographic_scope(event: dict) -> None:
    location = event.get("location") or {}
    city = normalized(location.get("city"))
    if city in {"gijon", "gijon / xixon", "xixon"}:
        return

    category = (event.get("primary_category") or {}).get("id")
    region = normalized(location.get("region"))
    assert category == "deporte-bienestar", f"non-Gijon cultural event leaked into dataset: {event.get('title')}"
    assert region == "asturias", f"regional sport must remain in Asturias: {event.get('title')}"
    title = normalized(event.get("title"))
    assert "futbol" not in title and "futsal" not in title, f"regional football must stay excluded: {event.get('title')}"


def check_gijon_dataset() -> None:
    data = validate_dataset(APP / "data/gijon/agenda_web.json")
    assert data.get("schema_version") == "1.3.0"
    assert data.get("timezone") == "Europe/Madrid"

    source_ids = {
        source.get("id")
        for source in data.get("sources", [])
        if isinstance(source, dict)
    }
    assert {
        "gijon_opendata_events",
        "la_revoltosa_gijon",
        "toma3_xixon",
        "meidinerz_jazz_club",
        "cafe_dindurra",
        "agenda_gijon",
        "ciclismo_asturias",
        "turismo_asturias_deporte",
    } <= source_ids

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
        check_gijon_geographic_scope(event)
        assert event.get("event_type") in {"event", "course", "program", "flexible_offer"}
        # `event_type` is the canonical semantic field. `editorial.classification`
        # is explanatory metadata produced by some sources, so it may be absent;
        # when present it must agree with the canonical type.
        editorial = event.get("editorial") or {}
        classification = editorial.get("classification")
        if classification is not None:
            assert classification == event.get("event_type"), (
                f"{event.get('id')} ({event.get('title')}): editorial classification "
                f"{classification!r} != event_type {event.get('event_type')!r}"
            )


def check_valparaiso_dataset_compatibility() -> None:
    data = validate_dataset(ROOT / "agenda_web.json")
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
    check_exhibition_layout_guard()
    check_gijon_dataset()
    check_valparaiso_dataset_compatibility()
    check_gijon_source_path()
    check_duplicate_public_writer_retired()
    print("Joint multi-city pre-release contract: OK")


if __name__ == "__main__":
    main()
