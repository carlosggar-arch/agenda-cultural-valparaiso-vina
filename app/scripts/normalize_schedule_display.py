from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
GIJON_DATASET_PATH = ROOT / "app" / "data" / "gijon" / "agenda_web.json"
CLOCK_RE = re.compile(r"\b(?:[01]\d|2[0-3]):[0-5]\d\b")
ISO_CLOCK_RE = re.compile(r"T((?:[01]\d|2[0-3]):[0-5]\d)")
TWO_TIME_COMMA_RE = re.compile(
    r"\b((?:[01]\d|2[0-3]):[0-5]\d)\s*,\s*((?:[01]\d|2[0-3]):[0-5]\d)\b"
)


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


def structured_session_starts(schedule: dict) -> set[tuple[str, str]]:
    starts: set[tuple[str, str]] = set()
    for occurrence in schedule.get("occurrences") or []:
        if not isinstance(occurrence, dict):
            continue
        occurrence_day = day(occurrence.get("start"))
        occurrence_clock = iso_clock(occurrence.get("start"))
        if occurrence_day and occurrence_clock:
            starts.add((occurrence_day, occurrence_clock))
    return starts


def has_multiple_structured_sessions(schedule: dict) -> bool:
    return len(structured_session_starts(schedule)) >= 2


def simple_two_clock_interval(schedule: dict) -> str | None:
    """Return HH:MM–HH:MM when a flat two-clock list is start/end.

    Public presentation rule for Valparaíso/Viña and Gijón:
    - exactly two ordered comma-separated clock values;
    - no structured evidence of independent sessions;
    - when a timed structured start exists, it must match the first clock.

    A single known clock is left as start-only. We never invent a closing time.
    """
    display = str(schedule.get("display_text") or "").strip()
    clocks = CLOCK_RE.findall(display)
    if len(clocks) != 2 or clocks == ["00:00", "23:59"]:
        return None
    if not TWO_TIME_COMMA_RE.search(display):
        return None
    if has_multiple_structured_sessions(schedule):
        return None
    first, second = clocks
    if minutes(first) >= minutes(second):
        return None
    structured_start = iso_clock(schedule.get("start"))
    if structured_start and structured_start != first:
        return None
    return f"{first}–{second}"


def paired_flattened_ranges(schedule: dict) -> list[str] | None:
    if schedule.get("mode") != "multi_day":
        return None
    display = str(schedule.get("display_text") or "").strip()
    clocks = CLOCK_RE.findall(display)
    if len(clocks) != 4 or has_multiple_structured_sessions(schedule):
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
        return sorted(set(changes))

    opening_hours = schedule.get("opening_hours")
    opening_text = str(opening_hours.get("display_text") or "").strip() if isinstance(opening_hours, dict) else ""
    if opening_text and range_text:
        if schedule.get("mode") == "multi_day" and schedule.get("display_text") != range_text:
            schedule["display_text"] = range_text
            changes.append("display_text")
        return sorted(set(changes))

    interval = simple_two_clock_interval(schedule)
    if interval and range_text:
        normalized = f"{range_text} · {interval}"
        if schedule.get("display_text") != normalized:
            schedule["display_text"] = normalized
            changes.append("display_text")
        return sorted(set(changes))

    ranges = paired_flattened_ranges(schedule)
    if ranges and range_text:
        normalized = f"{range_text} · {' · '.join(ranges)}"
        if schedule.get("display_text") != normalized:
            schedule["display_text"] = normalized
            changes.append("display_text")

    return sorted(set(changes))


def strip_private_editorial(value: object) -> int:
    """Remove private review metadata at the canonical public projection."""
    removed = 0
    if isinstance(value, dict):
        if "editorial" in value:
            value.pop("editorial")
            removed += 1
        for child in value.values():
            removed += strip_private_editorial(child)
    elif isinstance(value, list):
        for child in value:
            removed += strip_private_editorial(child)
    return removed


def normalize_dataset(dataset: dict) -> tuple[dict, list[dict], int]:
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
    removed_editorial = strip_private_editorial(output)
    return output, rows, removed_editorial


def dataset_targets(primary: Path, *, include_sibling_cities: bool = False) -> list[Path]:
    """Return only explicitly selected datasets.

    A single-city publication must never mutate a sibling city merely because
    the selected file happens to be the repository-root dataset. Multi-city
    normalization is therefore opt-in and explicit.
    """
    targets = [primary]
    if not include_sibling_cities:
        return targets
    try:
        is_public_root = primary.resolve() == DATASET_PATH.resolve()
    except OSError:
        is_public_root = primary == DATASET_PATH
    if is_public_root and GIJON_DATASET_PATH.exists():
        targets.append(GIJON_DATASET_PATH)
    return targets


def dataset_label(dataset_path: Path) -> str:
    """Return a stable display label for relative or absolute dataset paths."""
    resolved = dataset_path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize schedule presentation noise without fetching sources.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument(
        "--all-datasets",
        action="store_true",
        help="Explicitly include configured sibling-city datasets; never implied by --dataset.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if normalization would change any selected dataset.")
    args = parser.parse_args()

    changed_any = False
    summaries: list[dict] = []
    for dataset_path in dataset_targets(args.dataset, include_sibling_cities=args.all_datasets):
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        normalized, rows, removed_editorial = normalize_dataset(dataset)
        summaries.append({
            "dataset": dataset_label(dataset_path),
            "normalized_events": len(rows),
            "private_editorial_fields_removed": removed_editorial,
            "rows": rows,
        })
        changed = bool(rows) or bool(removed_editorial)
        changed_any = changed_any or changed
        if changed and not args.check:
            dataset_path.write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

    print(json.dumps({"datasets": summaries}, ensure_ascii=False, indent=2))
    if args.check and changed_any:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
