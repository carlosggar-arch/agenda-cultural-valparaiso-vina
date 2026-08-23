from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = {
    "valparaiso": ROOT / "agenda_web.json",
    "gijon": ROOT / "app/data/gijon/agenda_web.json",
}
REGISTRY = ROOT / "app/data/venue-registry.json"


def fold(value: object) -> str:
    text = str(value or "").strip().lower()
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def finite(value: object, low: float, high: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def useful_address(location: dict) -> str | None:
    address = str(location.get("address") or "").strip()
    if not address:
        return None
    normalized = fold(address)
    if normalized in {"por confirmar", "sin direccion", "direccion por confirmar", "lugar por confirmar"}:
        return None
    city = fold(location.get("city") or location.get("commune"))
    if city and normalized == city:
        return None
    return address


def verified_location(event: dict) -> bool:
    location = event.get("location") or {}
    verification = location.get("verification") or {}
    public_status = event.get("public_status") or {}
    if public_status.get("source_official") is True:
        return True
    if location.get("address_verified") is True or location.get("coordinates_verified") is True:
        return True
    if isinstance(verification, dict):
        if verification.get("verified") is True:
            return True
        if str(verification.get("status") or "").strip().lower() == "verified":
            return True
    if isinstance(verification, str) and verification.strip().lower().startswith("verified"):
        return True
    return False


def event_has_map(event: dict) -> bool:
    location = event.get("location") or {}
    if location.get("online") is True or not verified_location(event):
        return False
    lat = finite(location.get("latitude"), -90, 90)
    lon = finite(location.get("longitude"), -180, 180)
    if lat is not None and lon is not None and not (lat == 0 and lon == 0):
        return True
    city = str(location.get("city") or location.get("commune") or "").strip()
    return bool(city and useful_address(location))


def registry_payload() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8")).get("venues", [])


def city_compatible(record: dict, city: str) -> bool:
    folded = fold(city)
    candidates = [fold(value) for value in record.get("city_names", []) if fold(value)]
    if not folded or not candidates:
        return True
    return any(candidate == folded or candidate in folded or folded in candidate for candidate in candidates)


def without_exact_city_suffix(venue: str, city: str) -> str:
    value = fold(venue)
    city_folded = fold(city)
    if not value or not city_folded or value == city_folded:
        return value
    suffix = f" {city_folded}"
    return value[:-len(suffix)].strip() if value.endswith(suffix) else value


def registry_record_for(venue: str, city: str, records: list[dict]) -> dict | None:
    value = fold(venue)
    trimmed = without_exact_city_suffix(venue, city)
    for record in records:
        if not city_compatible(record, city):
            continue
        aliases = {fold(record.get("canonical_name")), *(fold(alias) for alias in record.get("aliases", []))}
        aliases.discard("")
        if value in aliases or (trimmed != value and trimmed in aliases):
            return record
    return None


def registry_has_verified_location(record: dict | None) -> bool:
    if not record:
        return False
    address = str(record.get("address") or "").strip()
    coords = record.get("coordinates") or {}
    lat = finite(coords.get("latitude"), -90, 90)
    lon = finite(coords.get("longitude"), -180, 180)
    has_coords = lat is not None and lon is not None and not (lat == 0 and lon == 0)
    return bool(
        (address or has_coords)
        and str(record.get("location_source_url") or "").strip()
        and str(record.get("location_verified_at") or "").strip()
    )


def main() -> None:
    records = registry_payload()
    groups: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "count": 0,
        "mapped": 0,
        "raw_mapped": 0,
        "registry_mapped": 0,
        "addresses": set(),
        "coordinates": set(),
        "official": 0,
        "ids": [],
        "record": None,
    })

    for city_id, path in DATASETS.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for event in payload.get("events", []):
            location = event.get("location") or {}
            venue = str(location.get("venue") or "").strip()
            if not venue or location.get("online") is True:
                continue
            city = str(location.get("city") or location.get("commune") or city_id).strip()
            key = (city, venue)
            row = groups[key]
            row["count"] += 1
            raw_mapped = event_has_map(event)
            record = registry_record_for(venue, city, records)
            registry_mapped = registry_has_verified_location(record)
            row["raw_mapped"] += int(raw_mapped)
            row["registry_mapped"] += int(not raw_mapped and registry_mapped)
            row["mapped"] += int(raw_mapped or registry_mapped)
            row["record"] = record or row["record"]
            row["official"] += int((event.get("public_status") or {}).get("source_official") is True)
            address = useful_address(location)
            if address:
                row["addresses"].add(address)
            lat = finite(location.get("latitude"), -90, 90)
            lon = finite(location.get("longitude"), -180, 180)
            if lat is not None and lon is not None:
                row["coordinates"].add(f"{lat},{lon}")
            if len(row["ids"]) < 3:
                row["ids"].append(str(event.get("id") or ""))

    print("MAP_LOCATION_AUDIT_BEGIN")
    missing = []
    for (city, venue), row in sorted(groups.items(), key=lambda item: (fold(item[0][0]), fold(item[0][1]))):
        record = row["record"]
        registry_address = str((record or {}).get("address") or "").strip()
        registry_coords = (record or {}).get("coordinates") or {}
        status = "OK" if row["mapped"] == row["count"] else "PARTIAL" if row["mapped"] else "MISSING"
        if status != "OK":
            missing.append((city, venue))
        print(json.dumps({
            "status": status,
            "city": city,
            "venue": venue,
            "events": row["count"],
            "events_with_map_after_enrichment": row["mapped"],
            "raw_event_maps": row["raw_mapped"],
            "registry_added_maps": row["registry_mapped"],
            "official_events": row["official"],
            "event_addresses": sorted(row["addresses"]),
            "event_coordinates": sorted(row["coordinates"]),
            "registry_id": (record or {}).get("id"),
            "registry_address": registry_address or None,
            "registry_coordinates": registry_coords or None,
            "registry_location_source": (record or {}).get("location_source_url"),
            "sample_event_ids": row["ids"],
        }, ensure_ascii=False))
    print(f"MAP_LOCATION_AUDIT_SUMMARY venues={len(groups)} missing_or_partial={len(missing)}")
    print("MAP_LOCATION_AUDIT_END")


if __name__ == "__main__":
    main()
