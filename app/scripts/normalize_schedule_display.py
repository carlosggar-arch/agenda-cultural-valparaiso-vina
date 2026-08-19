from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
CLOCK_RE = re.compile(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b")
ISO_CLOCK_RE = re.compile(r"T((?:[01]\d|2[0-3]):[0-5]\d)")


def day(value: object) -> str | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def iso_clock(value: object) -> str | None:
    match = ISO_CLOCK_RE.search(str(value or ""))
    return match.group(1) if match else None


def minutes(clock: str) -> int:
    hour, minute = clock.split(":", 1)
    return int(hour) * 60 + int(minute)


def date_range_text(schedule: dict) -> str | None:
    start_day = day(schedule.get("start") or (schedule.get("occurrences") or [{}])[0].get("start"))
    end_day = day(schedule.get("end") or (schedule.get("occurrences") or [{}])[0].get("end"))
    if not start_day:
        return None
    if end_day and end_day != start_day:
        return f"{start_day} – {end_day}"
    return start_day


def paired_flattened_ranges(schedule: dict) -> list[str] | None:
    if schedule.get("mode") != "multi_day":
        return None
    display = str(schedule.get("display_text") or "").strip()
    clocks = CLOCK_RE.findall(display)
    if len(clocks) != 4:
        return None
    start_day = day(schedule.get("start"))
    end_day = day(schedule.get("end"))
    if not start_day or not end_day or start_day == end_day:
        return None
    if iso_clock(schedule.get("start")) != clocks[0]:
        return None
    if not (minutes(clocks[0]) < minutes(clocks[1]) and minutes(clocks[2]) < minutes(clocks[3])):
        return None
    return [f"{clocks[0]}–{clocks[1]}", f"{clocks[2]}–{clocks[3]}"]


def all_day_sentinel(schedule: dict) -> bool:
    display = str(schedule.get("display_text") or "")
    clocks = CLOCK_RE.findall(display)
    return clocks == ["00:00", "23:59"]


def normalize_schedule(schedule: dict) -> list[str]:
    changes: list[str] = []
    range_text = date_range_text(schedule)

    if all_day_sentinel(schedule) and range_text:
        if schedule.get("display_text") != range_text:
            schedule["display_text"] = range_text
            changes.append("display_text")
        start = str(schedule.get("start") or "")
        end = str(schedule.get("end") or "")
        if iso_clock(start) == "00:00":
            schedule["start"] = day(start)
            changes.append("start")
        if iso_clock(end) == "23:59":
            schedule["end"] = day(end)
            changes.append("end")
        return changes

    ranges = paired_flattened_ranges(schedule)
    if ranges and range_text:
        normalized = f"{range_text} · {' · '.join(ranges)}"
        if schedule.get("display_text") != normalized:
            schedule["display_text"] = normalized
            changes.append("display_text")

    opening_hours = schedule.get("opening_hours")
    opening_text = str(opening_hours.get("display_text") or "").strip() if isinstance(opening_hours, dict) else ""
    if opening_text and range_text:
        # Opening hours have their own authoritative field. Keep the event
        # display_text date-only so start/end edge clocks cannot masquerade as
        # a continuous multi-day event interval.
        if schedule.get("mode") == "multi_day" and schedule.get("display_text") != range_text:
            schedule["display_text"] = range_text
            changes.append("display_text")

    return sorted(set(changes))


def normalize_dataset(dataset: dict) -> tuple[dict, list[dict]]:
    output = copy.deepcopy(dataset)
    rows: list[dict] = []
    for event in output.get("events") or []:
        if not isinstance(event, dict):
            continue
        schedule = event.get("schedule")
        if not isinstance(schedule, dict):
            continue
        fields = normalize_schedule(schedule)
        if fields:
            rows.append({"id": event.get("id"), "title": event.get("title"), "fields": fields})
    return output, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize schedule presentation noise without fetching sources.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--check", action="store_true", help="Fail if normalization would change the dataset.")
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    normalized, rows = normalize_dataset(dataset)
    print(json.dumps({"normalized_events": len(rows), "rows": rows}, ensure_ascii=False, indent=2))

    if args.check:
        raise SystemExit(1 if rows else 0)
    if rows:
        args.dataset.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
