from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
DATASET = APP / "data" / "gijon" / "agenda_web.json"

REQUIRED_SOURCE_IDS = {
    "gijon_opendata_events",
    "juventud_gijon",
    "la_revoltosa_gijon",
    "toma3_xixon",
    "meidinerz_jazz_club",
    "cafe_dindurra",
    "laboral_ciudad_cultura",
    "laboral_centro_arte",
    "teatro_albeniz_gijon",
    "bioparc_acuario_gijon",
    "jardin_botanico_atlantico",
    "ateneo_jovellanos",
    "sala_acapulco_conciertos",
    "la_caja_de_musicos",
    "agenda_gijon",
    "ciclismo_asturias",
    "turismo_asturias_deporte",
}


def clean(value) -> str:
    return " ".join(str(value or "").split())


def folded(value) -> str:
    text = unicodedata.normalize("NFD", clean(value).casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def valid_http_url(value) -> bool:
    try:
        parsed = urlparse(clean(value))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def duplicate_signature(event: dict) -> tuple[str, str, str]:
    schedule = event.get("schedule") or {}
    location = event.get("location") or {}
    return (
        re.sub(r"\W+", " ", folded(event.get("title"))).strip(),
        clean(schedule.get("start")),
        re.sub(r"\W+", " ", folded(location.get("venue"))).strip(),
    )


def assert_runtime_contract() -> dict[str, bool]:
    index = (APP / "index.html").read_text(encoding="utf-8")
    app_js = (APP / "app.js").read_text(encoding="utf-8")
    pwa_js = (APP / "pwa.js").read_text(encoding="utf-8")
    first_run = (APP / "city-first-run.js").read_text(encoding="utf-8")
    favorites = (APP / "favorites.js").read_text(encoding="utf-8")
    plan_ahead = (APP / "plan-ahead.js").read_text(encoding="utf-8")

    checks = {
        "manual_city_choice": (
            'data-city-option="valparaiso"' in index
            and 'data-city-option="gijon"' in index
        ),
        "location_choice": (
            "data-use-location" in index
            and "navigator.geolocation.getCurrentPosition" in app_js
            and "suggestCityFromCoordinates" in app_js
        ),
        "city_persistence": (
            'const STORAGE_KEY = "agenda-cultural-city"' in app_js
            and "localStorage.setItem(STORAGE_KEY" in app_js
        ),
        "first_run_city_flow": (
            "city-first-run.js" in index
            and "agenda-cultural-city" in first_run
        ),
        "favorites_wired": (
            'import "./favorites.js";' in pwa_js
            and "FAVORITES_STORAGE_KEY" in favorites
            and "data-my-plans" in favorites
        ),
        "plan_ahead_wired": (
            'import "./plan-ahead.js";' in pwa_js
            and "selectPlanAhead" in plan_ahead
        ),
        "mobile_experience_wired": 'import "./mobile-experience.js";' in pwa_js,
        "single_shell_two_datasets": (
            'dataset: "../agenda_web.json"' in app_js
            and 'dataset: "./data/gijon/agenda_web.json"' in app_js
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise AssertionError(f"PWA multi-city V1 contract failed: {failed}")
    return checks


def main() -> None:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    events = [event for event in payload.get("events", []) if isinstance(event, dict)]
    sources = [source for source in payload.get("sources", []) if isinstance(source, dict)]
    if not events:
        raise AssertionError("Gijon V1 dataset is empty")

    ids = [clean(event.get("id")) for event in events]
    if any(not event_id for event_id in ids):
        raise AssertionError("Gijon V1 contains events without id")
    duplicate_ids = [event_id for event_id, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        raise AssertionError(f"Duplicate event ids: {duplicate_ids}")

    signatures = [duplicate_signature(event) for event in events]
    duplicate_signatures = [signature for signature, count in Counter(signatures).items() if count > 1]
    if duplicate_signatures:
        raise AssertionError(f"Duplicate title/start/venue signatures: {duplicate_signatures[:8]}")

    invalid_links = []
    missing_images = []
    actionable_content = []
    actionable_time = []
    bad_opendata_aliases = []
    for event in events:
        event_id = clean(event.get("id"))
        links = event.get("links") if isinstance(event.get("links"), dict) else {}
        official = clean(links.get("official"))
        if not valid_http_url(official):
            invalid_links.append((event_id, official))

        image = event.get("image") if isinstance(event.get("image"), dict) else {}
        if not valid_http_url(image.get("url")):
            missing_images.append(event_id)

        status = event.get("public_status") if isinstance(event.get("public_status"), dict) else {}
        if status.get("content_followup_needed") is True:
            actionable_content.append(event_id)
        if status.get("time_followup_needed") is True:
            actionable_time.append(event_id)

        if event.get("source_id") == "gijon_opendata_events":
            municipal_page = clean(links.get("municipal_page")).rstrip("/")
            if municipal_page:
                for key in ("official", "source"):
                    candidate = clean(links.get(key)).rstrip("/")
                    if candidate and candidate == municipal_page:
                        bad_opendata_aliases.append((event_id, key, candidate))

    if invalid_links:
        raise AssertionError(f"Invalid official links: {invalid_links[:8]}")
    if missing_images:
        raise AssertionError(f"Events without usable images: {missing_images[:8]}")
    if actionable_content:
        raise AssertionError(f"Actionable content defects remain: {actionable_content[:8]}")
    if actionable_time:
        raise AssertionError(f"Actionable time defects remain: {actionable_time[:8]}")
    if bad_opendata_aliases:
        raise AssertionError(f"Unstable gijon.es aliases exposed as official/source: {bad_opendata_aliases[:8]}")

    source_ids = {clean(source.get("id")) for source in sources}
    missing_sources = sorted(REQUIRED_SOURCE_IDS - source_ids)
    if missing_sources:
        raise AssertionError(f"Required Gijon sources missing: {missing_sources}")

    actionable_zero = []
    for source in sources:
        diagnostics = source.get("diagnostics") if isinstance(source.get("diagnostics"), dict) else {}
        if diagnostics.get("actionable_zero") is True:
            actionable_zero.append(clean(source.get("id")))
    if actionable_zero:
        raise AssertionError(f"Sources with unresolved zero-event coverage: {actionable_zero}")

    critical = {source.get("id"): source for source in sources if source.get("id") in {"gijon_opendata_events", "laboral_centro_arte"}}
    for source_id in ("gijon_opendata_events", "laboral_centro_arte"):
        source = critical.get(source_id)
        if not source:
            raise AssertionError(f"Critical source absent: {source_id}")
        if clean(source.get("status")).casefold() == "error":
            raise AssertionError(f"Critical source is in error: {source_id}: {source.get('detail')}")

    expected_counts = {
        "total": len(events),
        "events": sum(event.get("event_type") == "event" for event in events),
        "courses": sum(event.get("event_type") == "course" for event in events),
        "flexible_offers": sum(event.get("event_type") == "flexible_offer" for event in events),
        "programs": sum(event.get("event_type") == "program" for event in events),
    }
    if payload.get("counts") != expected_counts:
        raise AssertionError(f"Count metadata mismatch: {payload.get('counts')} != {expected_counts}")

    runtime = assert_runtime_contract()
    external_time_pending = sum(
        (event.get("public_status") or {}).get("time_external_update_pending") is True
        for event in events
    )
    opendata_fallback = sum(
        (event.get("public_status") or {}).get("external_link_quality") == "opendata_fallback"
        for event in events
    )
    report = {
        "stable": True,
        "events": len(events),
        "sources": len(sources),
        "duplicates": 0,
        "invalid_official_links": 0,
        "missing_images": 0,
        "actionable_content": 0,
        "actionable_time": 0,
        "actionable_zero_sources": 0,
        "external_time_pending_allowed": external_time_pending,
        "opendata_fallback_allowed": opendata_fallback,
        "laboral_centro_arte_events": int(critical["laboral_centro_arte"].get("event_count") or 0),
        "runtime_contracts": sorted(runtime),
    }
    print("GIJON_V1_STABLE " + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
