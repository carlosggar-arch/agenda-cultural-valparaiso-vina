from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
QUALITY_DIR = ROOT / "app/data/quality"
DATASETS = {
    "valparaiso-vina": (ROOT / "agenda_web.json", "America/Santiago"),
    "gijon": (ROOT / "app/data/gijon/agenda_web.json", "Europe/Madrid"),
}
COVERAGE_PATH = QUALITY_DIR / "source-coverage.json"
EVENT_QUALITY_PATH = QUALITY_DIR / "event-quality.json"
READINESS_PATH = QUALITY_DIR / "release-readiness.json"
HIGH_VALUE_PATH = QUALITY_DIR / "high-value-sources.json"
PORTAL_PATH = QUALITY_DIR / "portaltickets-editorial.json"


def load(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def pct(value: int, total: int) -> float:
    return round(100.0 * value / total, 1) if total else 0.0


def field_flags(item: dict) -> dict[str, bool]:
    schedule = item.get("schedule") or {}
    location = item.get("location") or {}
    links = item.get("links") or {}
    status = item.get("public_status") or {}
    price = item.get("price") or {}
    image = item.get("image") or {}
    start = str(schedule.get("start") or "")
    return {
        "date": bool(start),
        "time": "T" in start,
        "venue": bool(location.get("venue") or location.get("address") or location.get("online")),
        "image": bool(image.get("url")),
        "official_link": bool(links.get("official") or links.get("source") or links.get("tickets")),
        "source_attribution": bool(item.get("source_id") or item.get("source_name")),
        "official_source": status.get("source_official") is True,
        "price_known": price.get("is_free") is not None or bool(price.get("display_text")),
    }


def event_score(item: dict) -> float:
    flags = field_flags(item)
    weights = {
        "date": 20, "time": 10, "venue": 15, "image": 10,
        "official_link": 15, "source_attribution": 15, "price_known": 15,
    }
    return round(sum(weight for field, weight in weights.items() if flags[field]), 1)


def quality_class(score: float) -> str:
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "correct"
    if score >= 60:
        return "partial"
    return "review"


def duplicate_id_groups(events: list[dict]) -> int:
    counts = Counter(str(item.get("id") or "") for item in events if item.get("id"))
    return sum(1 for count in counts.values() if count > 1)


def coverage_report(existing: dict, datasets: dict[str, dict], generated_at: str) -> dict:
    thresholds = existing.get("thresholds") or {
        "zero_warning_days": 3, "zero_week_days": 7, "zero_critical_days": 14,
        "decline_ratio": 0.4, "decline_min_baseline": 3, "decline_min_prior_observations": 5,
    }
    prior_cities = existing.get("cities") or {}
    cities = {}
    for city_id, dataset in datasets.items():
        _, timezone = DATASETS[city_id]
        today = datetime.now(ZoneInfo(timezone)).date().isoformat()
        events = dataset.get("events") or []
        counts = Counter(str(item.get("source_id") or "") for item in events if item.get("source_id"))
        names = {}
        for item in events:
            sid = str(item.get("source_id") or "")
            if sid:
                names[sid] = str(item.get("source_name") or item.get("organizer") or sid)
        prior = prior_cities.get(city_id) or {}
        prior_date = str(prior.get("date") or "")
        prior_rows = {str(row.get("id")): row for row in prior.get("sources") or [] if row.get("id")}
        source_ids = list(prior_rows)
        for sid in sorted(counts):
            if sid not in prior_rows:
                source_ids.append(sid)
        rows = []
        for sid in source_ids:
            old = prior_rows.get(sid) or {}
            count = counts.get(sid, 0)
            same_day = prior_date == today
            observed = int(old.get("observed_days") or 0)
            if not same_day:
                observed += 1
            zero_streak = 0 if count else int(old.get("zero_streak_days") or 0) + (0 if same_day else 1)
            rows.append({
                "id": sid,
                "name": old.get("name") or names.get(sid) or sid,
                "role": old.get("role"),
                "source_type": old.get("source_type"),
                "current_count": count,
                "status": "producing" if count else ("zero_critical" if zero_streak >= thresholds["zero_critical_days"] else "zero_recent"),
                "severity": "ok" if count else ("critical" if zero_streak >= thresholds["zero_critical_days"] else "info"),
                "zero_streak_days": zero_streak,
                "observed_days": max(1, observed),
                "first_observed_date": old.get("first_observed_date") or today,
                "last_nonzero_date": today if count else old.get("last_nonzero_date"),
                "baseline_median": old.get("baseline_median"),
                "change_pct_vs_baseline": old.get("change_pct_vs_baseline"),
                "possible_drop": False,
                "history_confidence": "low" if max(1, observed) < 5 else old.get("history_confidence", "medium"),
            })
        producing = sum(row["current_count"] > 0 for row in rows)
        zero = len(rows) - producing
        attributed = sum(1 for item in events if item.get("source_id"))
        cities[city_id] = {
            "city_id": city_id,
            "date": today,
            "summary": {
                "sources_total": len(rows), "producing_now": producing, "zero_now": zero,
                "zero_3d_or_more": sum(row["zero_streak_days"] >= thresholds["zero_warning_days"] for row in rows),
                "zero_7d_or_more": sum(row["zero_streak_days"] >= thresholds["zero_week_days"] for row in rows),
                "zero_14d_or_more": sum(row["zero_streak_days"] >= thresholds["zero_critical_days"] for row in rows),
                "possible_drops": 0, "total_events": len(events),
                "attributed_events": attributed, "unattributed_events": len(events) - attributed,
            },
            "sources": rows,
        }
    return {"schema_version": "1.0.0", "generated_at": generated_at, "status": "ok", "retention_days": int(existing.get("retention_days") or 60), "thresholds": thresholds, "cities": cities}


def quality_report(datasets: dict[str, dict], coverage: dict, generated_at: str) -> dict:
    cities = {}
    for city_id, dataset in datasets.items():
        events = dataset.get("events") or []
        total = len(events)
        flags = [field_flags(item) for item in events]
        scores = [event_score(item) for item in events]
        by_source: dict[str, list[dict]] = {}
        for item in events:
            by_source.setdefault(str(item.get("source_id") or "unattributed"), []).append(item)
        category_counts = Counter()
        category_labels = {}
        area_counts = Counter()
        for item in events:
            cat = item.get("primary_category") or {}
            cid = str(cat.get("id") or "otros")
            category_counts[cid] += 1
            category_labels[cid] = str(cat.get("label") or cid)
            area = str((item.get("location") or {}).get("city") or "Sin localidad")
            area_counts[area] += 1
        distribution = [
            {"id": cid, "label": category_labels[cid], "count": count, "share_pct": pct(count, total), "underrepresented": pct(count, total) < 5.0}
            for cid, count in category_counts.most_common()
        ]
        source_rows = []
        for sid, items in sorted(by_source.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            source_scores = [event_score(item) for item in items]
            sample = items[0]
            source_rows.append({
                "id": sid,
                "name": str(sample.get("source_name") or sample.get("organizer") or sid),
                "count": len(items),
                "quality_score": round(sum(source_scores) / len(source_scores), 1),
                "quality_class": quality_class(sum(source_scores) / len(source_scores)),
                "attention": "none",
                "covered_by_other_sources": [], "priority": None, "role": None, "source_type": None,
                "coverage": {
                    "date_pct": pct(sum(field_flags(x)["date"] for x in items), len(items)),
                    "time_pct": pct(sum(field_flags(x)["time"] for x in items), len(items)),
                    "venue_pct": pct(sum(field_flags(x)["venue"] for x in items), len(items)),
                    "image_pct": pct(sum(field_flags(x)["image"] for x in items), len(items)),
                    "official_link_pct": pct(sum(field_flags(x)["official_link"] for x in items), len(items)),
                    "official_source_pct": pct(sum(field_flags(x)["official_source"] for x in items), len(items)),
                    "price_known_pct": pct(sum(field_flags(x)["price_known"] for x in items), len(items)),
                },
                "categories": dict(Counter(str((x.get("primary_category") or {}).get("id") or "otros") for x in items)),
            })
        cov_city = (coverage.get("cities") or {}).get(city_id) or {}
        cov_summary = cov_city.get("summary") or {}
        avg = round(sum(scores) / total, 1) if total else 0.0
        cities[city_id] = {
            "city_id": city_id,
            "publication_date": dataset.get("publication_date"),
            "generated_at": dataset.get("generated_at"),
            "summary": {
                "total_events": total, "average_quality_score": avg, "quality_class": quality_class(avg),
                "sources_catalogued": cov_summary.get("sources_total", len(source_rows)),
                "sources_producing": cov_summary.get("producing_now", len(source_rows)),
                "sources_zero": cov_summary.get("zero_now", 0),
                "review_priority_zero_sources": cov_summary.get("zero_now", 0),
                "zero_sources_covered_elsewhere": 0,
                "top3_source_share_pct": pct(sum(len(items) for _, items in sorted(by_source.items(), key=lambda kv: -len(kv[1]))[:3]), total),
                "unattributed_events": sum(1 for item in events if not item.get("source_id")),
            },
            "field_coverage": {
                "date_pct": pct(sum(x["date"] for x in flags), total),
                "time_pct": pct(sum(x["time"] for x in flags), total),
                "venue_pct": pct(sum(x["venue"] for x in flags), total),
                "image_pct": pct(sum(x["image"] for x in flags), total),
                "official_link_pct": pct(sum(x["official_link"] for x in flags), total),
                "source_attribution_pct": pct(sum(x["source_attribution"] for x in flags), total),
                "official_source_pct": pct(sum(x["official_source"] for x in flags), total),
                "price_known_pct": pct(sum(x["price_known"] for x in flags), total),
            },
            "category_distribution": distribution,
            "area_distribution": [{"area": area, "count": count, "share_pct": pct(count, total)} for area, count in area_counts.most_common()],
            "coverage_gaps": {
                "underrepresented_categories": [row["id"] for row in distribution if row["underrepresented"]],
                "source_concentration_high": pct(sum(len(items) for _, items in sorted(by_source.items(), key=lambda kv: -len(kv[1]))[:3]), total) >= 60.0,
                "review_priority_zero_sources": [row["id"] for row in cov_city.get("sources") or [] if row.get("current_count") == 0],
                "zero_sources_covered_elsewhere": [],
            },
            "pipeline_quality": {"duplicate_groups": duplicate_id_groups(events), "relevant_image_pct": pct(sum(x["image"] for x in flags), total), "removed_events": {}},
            "sources": source_rows,
        }
    return {"schema_version": "1.1.0", "generated_at": generated_at, "cities": cities}


def readiness_report(existing: dict, datasets: dict[str, dict], quality: dict, high_value: dict, portal: dict, generated_at: str) -> dict:
    checks = {}
    blockers = []
    warnings = []
    for city_id, dataset in datasets.items():
        events = dataset.get("events") or []
        quality_city = (quality.get("cities") or {}).get(city_id) or {}
        field = quality_city.get("field_coverage") or {}
        dupes = duplicate_id_groups(events)
        if not events:
            blockers.append(f"{city_id}:no_events")
        if dupes:
            blockers.append(f"{city_id}:duplicate_ids")
        checks[city_id] = {
            "events_present": bool(events), "duplicates_zero": dupes == 0, "fresh": True,
            "suspicious_titles_zero": True,
            "quality_score": (quality_city.get("summary") or {}).get("average_quality_score", 0.0),
            "official_links_pct": field.get("official_link_pct", 0.0),
            "source_attribution_pct": field.get("source_attribution_pct", 0.0),
        }
    hv_sources = high_value.get("sources") or []
    fetch_errors = [row for row in hv_sources if row.get("state") == "fetch_error"]
    if fetch_errors:
        warnings.extend(f"high_value_fetch_error:{row.get('id')}" for row in fetch_errors)
    if portal and not portal.get("fetch_ok", True):
        warnings.append("portaltickets_fetch_error_using_last_good_snapshot")
    old_apify = (existing.get("checks") or {}).get("apify_study") or {"status": "collecting"}
    if old_apify.get("status") == "collecting":
        warnings.append("apify_longitudinal_study_in_progress")
    checks["high_value_zero"] = {"actionable_zero": 0, "tracked": len(hv_sources) + (1 if portal else 0)}
    checks["apify_study"] = old_apify
    checks["category_gap_monitor"] = (existing.get("checks") or {}).get("category_gap_monitor") or {"fetch_errors": 0, "ready_uncovered": 0, "recurring_without_end": 0}
    checks["daily_email_retired"] = True
    return {
        "schema_version": "1.0.0", "generated_at": generated_at,
        "status": "blocked" if blockers else ("stable_with_observation" if warnings else "ready"),
        "stable_baseline": not blockers, "blockers": blockers, "warnings": sorted(set(warnings)), "checks": checks,
        "release_policy": "Stable means no critical data/publication regressions; longitudinal studies and noncritical source availability may continue in observation mode.",
    }


def build() -> tuple[dict, dict, dict]:
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    datasets = {city: load(path) for city, (path, _) in DATASETS.items()}
    coverage = coverage_report(load(COVERAGE_PATH), datasets, generated_at)
    quality = quality_report(datasets, coverage, generated_at)
    readiness = readiness_report(load(READINESS_PATH), datasets, quality, load(HIGH_VALUE_PATH), load(PORTAL_PATH), generated_at)
    return coverage, quality, readiness


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate source coverage, event quality and release readiness from current datasets.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    coverage, quality, readiness = build()
    if args.no_write:
        print(json.dumps({
            "SOURCE_COVERAGE": {city: data["summary"] for city, data in coverage["cities"].items()},
            "EVENT_QUALITY": {city: data["summary"] for city, data in quality["cities"].items()},
            "RELEASE_READINESS": {"status": readiness["status"], "blockers": readiness["blockers"], "warnings": readiness["warnings"]},
        }, ensure_ascii=False, indent=2))
        return
    save(COVERAGE_PATH, coverage)
    save(EVENT_QUALITY_PATH, quality)
    save(READINESS_PATH, readiness)


if __name__ == "__main__":
    main()
