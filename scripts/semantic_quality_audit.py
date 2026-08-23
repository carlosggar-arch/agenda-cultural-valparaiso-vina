from __future__ import annotations

import argparse
import json
import posixpath
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.event_semantics import EVENT_SEMANTICS, build_event_semantics
from scripts.public_category_rules import fold

CITY_REGISTRY_PATH = "app/cities.json"


def _read_repo_json(path: str, ref: str | None = None) -> dict[str, Any]:
    if ref:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise FileNotFoundError(f"{ref}:{path}: {result.stderr.strip()}")
        return json.loads(result.stdout)
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _dataset_path(dataset: str) -> str:
    return posixpath.normpath(posixpath.join("app", str(dataset)))


def load_city_events(ref: str | None = None) -> list[dict[str, Any]]:
    registry = _read_repo_json(CITY_REGISTRY_PATH, ref)
    loaded: list[dict[str, Any]] = []
    for city in registry.get("cities", []):
        city_id = str(city.get("id") or "").strip()
        dataset = str(city.get("dataset") or "").strip()
        if not city_id or not dataset:
            continue
        path = _dataset_path(dataset)
        try:
            payload = _read_repo_json(path, ref)
        except FileNotFoundError:
            continue
        for event in payload.get("events", []):
            if isinstance(event, dict):
                loaded.append({"city_id": city_id, "event": event})
    return loaded


def _source_identity(city_id: str, event: dict[str, Any]) -> dict[str, str]:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    links = event.get("links") if isinstance(event.get("links"), dict) else {}
    name = str(
        event.get("source_name")
        or source.get("name")
        or event.get("organizer")
        or "Fuente desconocida"
    ).strip()
    url = str(
        event.get("source_url")
        or source.get("url")
        or links.get("source")
        or links.get("official")
        or ""
    ).strip()
    normalized = fold(name) or fold(url) or "unknown"
    return {
        "key": f"{city_id}::{normalized}",
        "name": name,
        "url": url,
    }


def _distribution(counter: Counter[str], total: int) -> dict[str, float]:
    if not total:
        return {}
    return {
        category: round(count / total, 6)
        for category, count in sorted(counter.items())
    }


def build_quality_snapshot(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    queue: list[dict[str, Any]] = []
    total = 0

    for item in items:
        city_id = str(item.get("city_id") or "")
        event = item.get("event") or {}
        semantics = build_event_semantics(event)
        total += 1
        source = _source_identity(city_id, event)
        bucket = sources.setdefault(
            source["key"],
            {
                "city_id": city_id,
                "source_name": source["name"],
                "source_url": source["url"],
                "total": 0,
                "unclassified": 0,
                "_categories": Counter(),
            },
        )
        bucket["total"] += 1
        category_id = semantics["category"]["id"]
        bucket["_categories"][category_id] += 1
        if semantics["classification_state"] == "unclassified":
            bucket["unclassified"] += 1
            queue.append(
                {
                    "city_id": city_id,
                    "event_id": str(event.get("id") or ""),
                    "title": str(event.get("title") or "").strip(),
                    "source_name": source["name"],
                    "source_url": source["url"],
                    "score": semantics["score"],
                    "candidates": [
                        {
                            "category": candidate["category"]["id"],
                            "score": candidate["score"],
                            "confidence": candidate["confidence"],
                        }
                        for candidate in semantics.get("domain_candidates", [])[:3]
                    ],
                    "evidence": semantics["evidence"],
                }
            )

    public_sources: dict[str, dict[str, Any]] = {}
    for key, bucket in sorted(sources.items()):
        count = int(bucket["total"])
        categories: Counter[str] = bucket.pop("_categories")
        dominant_category = None
        dominant_share = 0.0
        if categories and count:
            dominant_category, dominant_count = sorted(
                categories.items(), key=lambda item: (-item[1], item[0])
            )[0]
            dominant_share = dominant_count / count
        public_sources[key] = {
            **bucket,
            "unclassified_rate": round(bucket["unclassified"] / count, 6) if count else 0.0,
            "category_distribution": _distribution(categories, count),
            "dominant_category": dominant_category,
            "dominant_share": round(dominant_share, 6),
        }

    queue.sort(key=lambda item: (item["city_id"], item["source_name"], item["title"]))
    return {
        "total_events": total,
        "unclassified_count": len(queue),
        "unclassified_rate": round(len(queue) / total, 6) if total else 0.0,
        "sources": public_sources,
        "unclassified_queue": queue,
    }


def _distribution_drift(
    current: dict[str, float],
    baseline: dict[str, float],
) -> float:
    categories = set(current) | set(baseline)
    return 0.5 * sum(
        abs(float(current.get(category, 0.0)) - float(baseline.get(category, 0.0)))
        for category in categories
    )


def detect_source_anomalies(
    current: dict[str, Any],
    baseline: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not baseline:
        return []

    config = EVENT_SEMANTICS["quality"]
    minimum_events = int(config["minimum_events_for_source_anomaly"])
    warning_rate = float(config["unclassified_rate_warning"])
    critical_rate = float(config["unclassified_rate_critical"])
    delta_warning = float(config["unclassified_rate_delta_warning"])
    drift_warning = float(config["distribution_drift_warning"])
    dominant_threshold = float(config["dominant_share_threshold"])
    anomalies: list[dict[str, Any]] = []
    baseline_sources = baseline.get("sources", {})

    for key, now in current.get("sources", {}).items():
        if int(now.get("total", 0)) < minimum_events:
            continue
        before = baseline_sources.get(key)
        if before is None:
            if float(now.get("unclassified_rate", 0.0)) >= warning_rate:
                anomalies.append(
                    {
                        "type": "new_source_unclassified_rate",
                        "severity": (
                            "critical"
                            if float(now["unclassified_rate"]) >= critical_rate
                            else "warning"
                        ),
                        "source_key": key,
                        "city_id": now.get("city_id"),
                        "source_name": now.get("source_name"),
                        "current_rate": now.get("unclassified_rate"),
                    }
                )
            continue
        if int(before.get("total", 0)) < minimum_events:
            continue

        current_rate = float(now.get("unclassified_rate", 0.0))
        baseline_rate = float(before.get("unclassified_rate", 0.0))
        rate_delta = current_rate - baseline_rate
        if current_rate >= warning_rate and rate_delta >= delta_warning:
            anomalies.append(
                {
                    "type": "unclassified_rate_spike",
                    "severity": "critical" if current_rate >= critical_rate else "warning",
                    "source_key": key,
                    "city_id": now.get("city_id"),
                    "source_name": now.get("source_name"),
                    "baseline_rate": round(baseline_rate, 6),
                    "current_rate": round(current_rate, 6),
                    "delta": round(rate_delta, 6),
                }
            )

        drift = _distribution_drift(
            now.get("category_distribution", {}),
            before.get("category_distribution", {}),
        )
        if drift >= drift_warning:
            anomalies.append(
                {
                    "type": "category_distribution_drift",
                    "severity": "warning",
                    "source_key": key,
                    "city_id": now.get("city_id"),
                    "source_name": now.get("source_name"),
                    "drift": round(drift, 6),
                }
            )

        before_dominant = before.get("dominant_category")
        now_dominant = now.get("dominant_category")
        if (
            before_dominant
            and now_dominant
            and before_dominant != now_dominant
            and float(before.get("dominant_share", 0.0)) >= dominant_threshold
            and float(now.get("dominant_share", 0.0)) >= dominant_threshold
        ):
            anomalies.append(
                {
                    "type": "dominant_category_shift",
                    "severity": "warning",
                    "source_key": key,
                    "city_id": now.get("city_id"),
                    "source_name": now.get("source_name"),
                    "baseline_category": before_dominant,
                    "current_category": now_dominant,
                    "baseline_share": before.get("dominant_share"),
                    "current_share": now.get("dominant_share"),
                }
            )

    return sorted(
        anomalies,
        key=lambda item: (
            0 if item["severity"] == "critical" else 1,
            str(item.get("city_id") or ""),
            str(item.get("source_name") or ""),
            item["type"],
        ),
    )


def build_report(compare_ref: str | None = None) -> dict[str, Any]:
    current = build_quality_snapshot(load_city_events())
    baseline = None
    baseline_error = None
    if compare_ref:
        try:
            baseline = build_quality_snapshot(load_city_events(compare_ref))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            baseline_error = str(exc)

    anomalies = detect_source_anomalies(current, baseline)
    return {
        "schema_version": "1.0.0",
        "semantic_contract": EVENT_SEMANTICS["schema_version"],
        "compare_ref": compare_ref,
        "baseline_error": baseline_error,
        "summary": {
            "total_events": current["total_events"],
            "unclassified_count": current["unclassified_count"],
            "unclassified_rate": current["unclassified_rate"],
            "source_count": len(current["sources"]),
            "anomaly_count": len(anomalies),
            "critical_anomaly_count": sum(
                1 for item in anomalies if item["severity"] == "critical"
            ),
        },
        "unclassified_queue": current["unclassified_queue"],
        "source_metrics": current["sources"],
        "source_anomalies": anomalies,
    }


def _escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any], queue_limit: int = 50) -> str:
    summary = report["summary"]
    lines = [
        "# Semantic quality report",
        "",
        (
            f"- Eventos auditados: **{summary['total_events']}** · "
            f"sin clasificar: **{summary['unclassified_count']}** "
            f"({summary['unclassified_rate']:.1%}) · "
            f"fuentes: **{summary['source_count']}** · "
            f"anomalías: **{summary['anomaly_count']}**"
        ),
    ]
    if report.get("compare_ref"):
        lines.append(f"- Comparación: `{_escape(report['compare_ref'])}`")
    if report.get("baseline_error"):
        lines.append(f"- Baseline no disponible: `{_escape(report['baseline_error'])}`")

    lines.extend(["", "## Cola sin clasificar", ""])
    queue = report["unclassified_queue"][:queue_limit]
    if not queue:
        lines.append("No hay eventos sin clasificar.")
    else:
        lines.extend([
            "| Ciudad | Fuente | Evento | Candidatos |",
            "| --- | --- | --- | --- |",
        ])
        for item in queue:
            candidates = ", ".join(
                f"{candidate['category']} ({candidate['score']})"
                for candidate in item.get("candidates", [])
            ) or "—"
            lines.append(
                f"| {_escape(item['city_id'])} | {_escape(item['source_name'])} | "
                f"{_escape(item['title'])} | {_escape(candidates)} |"
            )
        if len(report["unclassified_queue"]) > queue_limit:
            lines.append(
                f"\n_Mostrando {queue_limit} de {len(report['unclassified_queue'])}; "
                "el JSON adjunto contiene la cola completa._"
            )

    lines.extend(["", "## Anomalías por fuente", ""])
    anomalies = report["source_anomalies"]
    if not anomalies:
        lines.append("No se detectaron anomalías respecto del baseline.")
    else:
        lines.extend([
            "| Severidad | Ciudad | Fuente | Tipo |",
            "| --- | --- | --- | --- |",
        ])
        for item in anomalies:
            lines.append(
                f"| {_escape(item['severity'])} | {_escape(item.get('city_id'))} | "
                f"{_escape(item.get('source_name'))} | {_escape(item['type'])} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare-ref", default=None)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--markdown-output", default=None)
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()

    report = build_report(args.compare_ref)
    if args.json_output:
        path = ROOT / args.json_output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_output:
        path = ROOT / args.markdown_output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report), encoding="utf-8")

    summary = report["summary"]
    print(
        "SEMANTIC_QUALITY "
        f"events={summary['total_events']} "
        f"unclassified={summary['unclassified_count']} "
        f"sources={summary['source_count']} "
        f"anomalies={summary['anomaly_count']} "
        f"critical={summary['critical_anomaly_count']}"
    )
    if args.fail_on_critical and summary["critical_anomaly_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
