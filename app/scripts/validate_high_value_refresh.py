from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASETS = {
    "valparaiso": ROOT / "agenda_web.json",
    "gijon": ROOT / "app/data/gijon/agenda_web.json",
}
MANAGED = {
    "portaltickets_valparaiso",
    "museo_maritimo_nacional",
    "museo_evaristo_valle",
    "museo_barjola",
    "ficx",
    "laboral_cinemateca",
}
VALPO_ALLOWED = {"valparaiso", "vina del mar"}
OUT_OF_SCOPE_MARKERS = {
    "san antonio", "casablanca", "limache", "quilpue", "villa alemana",
    "quintero", "puchuncavi", "concon", "el quisco", "el tabo", "algarrobo",
    "cartagena", "la ligua", "zapallar", "papudo", "olmue", "los andes", "san felipe",
}
SIMILARITY_THRESHOLD = 0.86


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def event_day(item: dict) -> str:
    return str((item.get("schedule") or {}).get("start") or "")[:10]


def event_end(item: dict) -> str:
    schedule = item.get("schedule") or {}
    return str(schedule.get("end") or schedule.get("start") or "")[:10]


def city(item: dict) -> str:
    return norm((item.get("location") or {}).get("city"))


def title(item: dict) -> str:
    return norm(item.get("title"))


def source_id(item: dict) -> str:
    return str(item.get("source_id") or "")


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    dataset["counts"] = {
        "total": len(events),
        "events": sum(item.get("event_type") == "event" for item in events),
        "courses": sum(item.get("event_type") == "course" for item in events),
        "flexible_offers": sum(item.get("event_type") == "flexible_offer" for item in events),
        "programs": sum(item.get("event_type") == "program" for item in events),
    }


def suspicious_geography(item: dict) -> bool:
    if source_id(item) != "portaltickets_valparaiso":
        return False
    if city(item) not in VALPO_ALLOWED:
        return True
    location = item.get("location") or {}
    haystack = norm(" ".join(str(location.get(key) or "") for key in ("venue", "address")))
    return any(marker in haystack for marker in OUT_OF_SCOPE_MARKERS)


def near_duplicate(candidate: dict, existing: list[dict]) -> bool:
    day = event_day(candidate)
    candidate_city = city(candidate)
    candidate_title = title(candidate)
    if not day or not candidate_title:
        return True
    for other in existing:
        if event_day(other) != day or city(other) != candidate_city:
            continue
        other_title = title(other)
        if not other_title:
            continue
        if candidate_title == other_title:
            return True
        if candidate_title in other_title or other_title in candidate_title:
            if min(len(candidate_title), len(other_title)) >= 12:
                return True
        if SequenceMatcher(None, candidate_title, other_title).ratio() >= SIMILARITY_THRESHOLD:
            return True
    return False


def validate_dataset(name: str, dataset: dict) -> dict:
    timezone = "America/Santiago" if name == "valparaiso" else "Europe/Madrid"
    today = datetime.now(ZoneInfo(timezone)).date().isoformat()
    base = [item for item in dataset.get("events", []) if source_id(item) not in MANAGED]
    managed = [item for item in dataset.get("events", []) if source_id(item) in MANAGED]
    kept: list[dict] = []
    dropped = {"expired": 0, "geography": 0, "duplicate": 0, "invalid": 0}

    for item in managed:
        if not title(item) or not event_day(item):
            dropped["invalid"] += 1
            continue
        if event_end(item) and event_end(item) < today:
            dropped["expired"] += 1
            continue
        if name == "valparaiso" and suspicious_geography(item):
            dropped["geography"] += 1
            continue
        if name == "gijon" and city(item) != "gijon":
            dropped["geography"] += 1
            continue
        if near_duplicate(item, base + kept):
            dropped["duplicate"] += 1
            continue
        kept.append(item)

    dataset["events"] = sorted(base + kept, key=lambda item: (event_day(item), str(item.get("title") or "")))
    ids = [str(item.get("id") or "") for item in dataset["events"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name}: duplicate event ids after supplemental validation")
    refresh_counts(dataset)
    return {"dataset": name, "managed_before": len(managed), "managed_kept": len(kept), "dropped": dropped}


def main() -> None:
    reports = []
    for name, path in DATASETS.items():
        dataset = json.loads(path.read_text(encoding="utf-8"))
        reports.append(validate_dataset(name, dataset))
        path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"HIGH_VALUE_REFRESH_VALIDATED": reports}, ensure_ascii=False))


if __name__ == "__main__":
    main()
