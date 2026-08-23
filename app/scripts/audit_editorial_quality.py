from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from apply_content_quality_guard import (
    CITY_REGISTRY,
    configured_datasets,
    clean_space,
    fold,
    is_exhibition,
    is_social_url,
    parse_schedule_date,
    source_url,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "app/data/quality/editorial-quality-audit.json"
TITLE_CHAR_LIMIT = 110
TITLE_WORD_LIMIT = 18
REPEATED_IMAGE_THRESHOLD = 3
CATEGORY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}


def issue(city_id: str, event: dict, code: str, severity: str, message: str, **details) -> dict:
    return {
        "city_id": city_id,
        "event_id": clean_space(event.get("id")),
        "title": clean_space(event.get("title")),
        "code": code,
        "severity": severity,
        "message": message,
        **details,
    }


def image_url(event: dict) -> str:
    image = event.get("image") or {}
    return clean_space(image.get("url"))


def normalized_image_url(event: dict) -> str:
    value = image_url(event)
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        return f"{parsed.scheme.casefold()}://{parsed.netloc.casefold()}{parsed.path}".rstrip("/")
    except Exception:
        return value.casefold()


def category_values(event: dict) -> tuple[str, str, list[str]]:
    primary = event.get("primary_category") or {}
    primary_id = clean_space(primary.get("id"))
    primary_label = clean_space(primary.get("label"))
    listed_ids = [clean_space(item.get("id")) for item in (event.get("categories") or []) if isinstance(item, dict)]
    return primary_id, primary_label, listed_ids


def event_date_key(event: dict) -> str:
    schedule = event.get("schedule") or {}
    occurrences = schedule.get("occurrences") or []
    candidate = occurrences[0].get("start") if occurrences and isinstance(occurrences[0], dict) else schedule.get("start")
    parsed = parse_schedule_date(candidate)
    return parsed.isoformat() if parsed else ""


def is_dated_event(event: dict) -> bool:
    event_type = fold(event.get("event_type"))
    if event_type in {"flexible offer", "flexible_offer", "permanent offer", "permanent_offer", "recurring offer", "recurring_offer"}:
        return False
    content_kind = clean_space(event.get("content_kind"))
    if content_kind in {"recurring_offer", "permanent_offer", "undated"}:
        return False
    schedule = event.get("schedule") or {}
    return bool(schedule.get("start") or schedule.get("occurrences") or content_kind in {"dated_event", "long_running_event"})


def audit_event(city_id: str, event: dict) -> list[dict]:
    issues: list[dict] = []
    title = clean_space(event.get("title"))
    words = title.split()
    if not title:
        issues.append(issue(city_id, event, "missing_title", "error", "El evento no tiene título público."))
    elif len(title) > TITLE_CHAR_LIMIT or len(words) > TITLE_WORD_LIMIT:
        issues.append(issue(
            city_id,
            event,
            "long_title",
            "warning",
            "El título es demasiado largo para una tarjeta pública.",
            characters=len(title),
            words=len(words),
        ))

    primary_id, primary_label, listed_ids = category_values(event)
    if not primary_id or not primary_label:
        issues.append(issue(city_id, event, "missing_primary_category", "error", "Falta la categoría pública principal."))
    else:
        if not CATEGORY_ID_RE.fullmatch(primary_id):
            issues.append(issue(
                city_id,
                event,
                "malformed_category_id",
                "warning",
                "El identificador de categoría no sigue el contrato slug compartido.",
                category_id=primary_id,
            ))
        if listed_ids and primary_id not in listed_ids:
            issues.append(issue(
                city_id,
                event,
                "category_inconsistent",
                "warning",
                "La categoría principal no aparece entre las categorías declaradas del evento.",
                category_id=primary_id,
            ))

    location = event.get("location") or {}
    venue = clean_space(location.get("venue"))
    if is_dated_event(event) and not venue:
        issues.append(issue(city_id, event, "missing_venue", "warning", "Una actividad fechada no tiene recinto o lugar definido."))

    schedule = event.get("schedule") or {}
    start = parse_schedule_date(schedule.get("start"))
    end = parse_schedule_date(schedule.get("end"))
    occurrences = schedule.get("occurrences") or []
    if is_dated_event(event) and not start and not occurrences:
        issues.append(issue(city_id, event, "missing_schedule", "error", "Una actividad fechada no tiene fecha ni ocurrencias."))
    if start and end and end < start:
        issues.append(issue(
            city_id,
            event,
            "schedule_end_before_start",
            "error",
            "La fecha final es anterior a la fecha inicial.",
            start=start.isoformat(),
            end=end.isoformat(),
        ))
    if is_exhibition(event) and start and end and end < start:
        issues.append(issue(
            city_id,
            event,
            "exhibition_date_incoherent",
            "error",
            "La exposición tiene un rango de fechas incoherente.",
            start=start.isoformat(),
            end=end.isoformat(),
        ))

    status = event.get("public_status") or {}
    url = source_url(event)
    if not url:
        issues.append(issue(city_id, event, "missing_source", "error", "El evento no tiene una fuente pública consultable."))
    elif status.get("source_official") is not True and is_social_url(url):
        issues.append(issue(
            city_id,
            event,
            "social_only_unverified_source",
            "warning",
            "La única fuente visible es social y no está marcada como oficial.",
            source_url=url,
        ))

    if venue and title and fold(venue) == fold(title):
        issues.append(issue(city_id, event, "title_matches_venue", "warning", "El título coincide con el recinto y puede ser un encabezado mal capturado."))

    return issues


def duplicate_issues(city_id: str, events: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for event in events:
        title = fold(event.get("title"))
        venue = fold((event.get("location") or {}).get("venue"))
        day = event_date_key(event)
        if title and venue:
            groups[(title, venue, day)].append(event)

    findings: list[dict] = []
    for (_, _, day), members in groups.items():
        if len(members) < 2:
            continue
        ids = [clean_space(member.get("id")) for member in members]
        for member in members:
            findings.append(issue(
                city_id,
                member,
                "suspected_duplicate",
                "warning",
                "Hay otra tarjeta con el mismo título, recinto y fecha.",
                date=day or None,
                related_event_ids=[value for value in ids if value and value != clean_space(member.get("id"))],
            ))
    return findings


def repeated_image_issues(city_id: str, events: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        key = normalized_image_url(event)
        if key:
            groups[key].append(event)

    findings: list[dict] = []
    for key, members in groups.items():
        distinct_titles = {fold(member.get("title")) for member in members if fold(member.get("title"))}
        if len(members) < REPEATED_IMAGE_THRESHOLD or len(distinct_titles) < 2:
            continue
        ids = [clean_space(member.get("id")) for member in members]
        for member in members:
            findings.append(issue(
                city_id,
                member,
                "repeated_image",
                "info",
                "La misma imagen se usa en varias actividades distintas.",
                image_url=key,
                shared_by_event_ids=ids,
            ))
    return findings


def audit_dataset(dataset: dict, city_id: str) -> dict:
    events = list(dataset.get("events") or [])
    issues: list[dict] = []
    for event in events:
        issues.extend(audit_event(city_id, event))
    issues.extend(duplicate_issues(city_id, events))
    issues.extend(repeated_image_issues(city_id, events))
    issues.sort(key=lambda item: (-SEVERITY_ORDER[item["severity"]], item["code"], item.get("event_id") or ""))
    counts = Counter(item["severity"] for item in issues)
    by_code = Counter(item["code"] for item in issues)
    return {
        "city_id": city_id,
        "events_audited": len(events),
        "issue_count": len(issues),
        "severity_counts": {level: counts.get(level, 0) for level in ("error", "warning", "info")},
        "code_counts": dict(sorted(by_code.items())),
        "issues": issues,
    }


def audit_configured_datasets() -> dict:
    reports = []
    for city_id, dataset_path in configured_datasets():
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        report = audit_dataset(dataset, city_id)
        report["dataset"] = str(dataset_path)
        reports.append(report)

    totals = Counter()
    for report in reports:
        totals.update(report["severity_counts"])
    return {
        "status": "ok" if totals.get("error", 0) == 0 else "issues_found",
        "mode": "all_cities",
        "registry": str(CITY_REGISTRY),
        "cities_audited": len(reports),
        "events_audited": sum(report["events_audited"] for report in reports),
        "severity_counts": {level: totals.get(level, 0) for level in ("error", "warning", "info")},
        "datasets": reports,
    }


def should_fail(report: dict, fail_on: str) -> bool:
    threshold = SEVERITY_ORDER.get(fail_on)
    if threshold is None:
        return False
    counts = report.get("severity_counts") or {}
    return any(counts.get(level, 0) > 0 for level, rank in SEVERITY_ORDER.items() if rank >= threshold)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit editorial quality across registered cultural agenda datasets.")
    parser.add_argument("--all-cities", action="store_true", help="Audit every dataset registered in app/cities.json.")
    parser.add_argument("--dataset", help="Audit one dataset path when --all-cities is not supplied.")
    parser.add_argument("--city-id", default="dataset")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--fail-on", choices=["none", "info", "warning", "error"], default="none")
    args = parser.parse_args()

    if args.all_cities:
        report = audit_configured_datasets()
    else:
        if not args.dataset:
            parser.error("--dataset is required unless --all-cities is used")
        dataset_path = Path(args.dataset)
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        report = audit_dataset(dataset, args.city_id)
        report["dataset"] = str(dataset_path)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if args.fail_on != "none" and should_fail(report, args.fail_on):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
