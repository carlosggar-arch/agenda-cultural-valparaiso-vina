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


def registry_index() -> dict[tuple[str, str], dict]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    index: dict[tuple[str, str], dict] = {}
    for record in payload.get("venues", []):
        cities = [fold(city) for city in record.get("city_names", [])] or [""]
        aliases = [record.get("canonical_name"), *(record.get("aliases") or [])]
        for city in cities:
            for alias in aliases:
                key = (city, fold(alias))
                if key[1]:
                    index[key] = record
    return index


def main() -> None:
    registry = registry_index()
    groups: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "count": 0,
        "mapped": 0,
        "addresses": set(),
        "coordinates": set(),
        "official": 0,
        "ids": [],
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
            row["mapped"] += int(event_has_map(event))
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
        city_fold = fold(city)
        record = registry.get((city_fold, fold(venue)))
        if not record:
            # tolerate Gijon/Gijon-Xixon and Valparaiso/Vina naming variants when registry aliases are exact
            matches = [value for (reg_city, alias), value in registry.items() if alias == fold(venue) and (not reg_city or reg_city in city_fold or city_fold in reg_city)]
            record = matches[0] if matches else None
        registry_address = str((record or {}).get("address") or "").strip()
        registry_coords = (record or {}).get("coordinates") or {}
        registry_has_location = bool(registry_address or (registry_coords.get("latitude") is not None and registry_coords.get("longitude") is not None))
        status = "OK" if row["mapped"] == row["count"] else "PARTIAL" if row["mapped"] else "MISSING"
        if status != "OK":
            missing.append((city, venue))
        print(json.dumps({
            "status": status,
            "city": city,
            "venue": venue,
            "events": row["count"],
            "events_with_map": row["mapped"],
            "official_events": row["official"],
            "event_addresses": sorted(row["addresses"]),
            "event_coordinates": sorted(row["coordinates"]),
            "registry_id": (record or {}).get("id"),
            "registry_address": registry_address or None,
            "registry_has_location": registry_has_location,
            "sample_event_ids": row["ids"],
        }, ensure_ascii=False))
    print(f"MAP_LOCATION_AUDIT_SUMMARY venues={len(groups)} missing_or_partial={len(missing)}")
    print("MAP_LOCATION_AUDIT_END")


if __name__ == "__main__":
    main()
