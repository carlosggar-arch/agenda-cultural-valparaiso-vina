from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from scripts.event_semantics import build_event_semantics
from scripts.semantic_quality_audit import _source_identity, load_city_events

ROOT = Path(__file__).resolve().parents[1]

# Diagnostic-only thresholds. They never change the public category; they only
# identify events and sources that deserve editorial review.
NARROW_MARGIN_POINTS = 30.0
MINIMUM_EVENTS_FOR_SOURCE_RISK = 4
UNCERTAIN_RATE_WARNING = 0.25
UNCERTAIN_RATE_CRITICAL = 0.50
UNCERTAIN_RATE_DELTA_WARNING = 0.20
LOW_CONFIDENCE_VALUES = {"low"}


def _rate(value: int, total: int) -> float:
    return round(value / total, 6) if total else 0.0


def _candidate_rows(semantics: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    rows = []
    for candidate in semantics.get("domain_candidates", [])[:limit]:
        rows.append(
            {
                "category": (candidate.get("category") or {}).get("id"),
                "score": float(candidate.get("score", 0)),
                "confidence": candidate.get("confidence"),
            }
        )
    return rows


def uncertainty_signals(semantics: dict[str, Any]) -> dict[str, Any]:
    """Return review signals without changing the classifier decision."""
    classified = semantics.get("classification_state") == "classified"
    confidence = str(semantics.get("confidence") or "")
    candidates = _candidate_rows(semantics)
    margin = None
    if len(candidates) >= 2:
        margin = round(float(candidates[0]["score"]) - float(candidates[1]["score"]), 3)

    low_confidence = classified and confidence in LOW_CONFIDENCE_VALUES
    narrow_margin = classified and margin is not None and margin <= NARROW_MARGIN_POINTS
    uncertain = bool(low_confidence or narrow_margin)
    reasons = []
    if low_confidence:
        reasons.append("low_confidence")
    if narrow_margin:
        reasons.append("narrow_margin")

    return {
        "classified": classified,
        "low_confidence": low_confidence,
        "narrow_margin": narrow_margin,
        "uncertain": uncertain,
        "margin": margin,
        "reasons": reasons,
        "candidates": candidates,
    }


def build_uncertainty_snapshot(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    total_events = 0
    classified_events = 0
    low_confidence_count = 0
    narrow_margin_count = 0
    uncertain_count = 0
    queue: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "city_id": "",
            "source_name": "",
            "source_url": "",
            "total_events": 0,
            "classified_events": 0,
            "low_confidence_count": 0,
            "narrow_margin_count": 0,
            "uncertain_count": 0,
        }
    )

    for item in items:
        city_id = str(item.get("city_id") or "")
        event = item.get("event") or {}
        semantics = build_event_semantics(event)
        signals = uncertainty_signals(semantics)
        source = _source_identity(city_id, event)
        bucket = sources[source["key"]]
        bucket["city_id"] = city_id
        bucket["source_name"] = source["name"]
        bucket["source_url"] = source["url"]
        bucket["total_events"] += 1
        total_events += 1

        if signals["classified"]:
            classified_events += 1
            bucket["classified_events"] += 1
        if signals["low_confidence"]:
            low_confidence_count += 1
            bucket["low_confidence_count"] += 1
        if signals["narrow_margin"]:
            narrow_margin_count += 1
            bucket["narrow_margin_count"] += 1
        if signals["uncertain"]:
            uncertain_count += 1
            bucket["uncertain_count"] += 1
            queue.append(
                {
                    "city_id": city_id,
                    "event_id": str(event.get("id") or ""),
                    "title": str(event.get("title") or "").strip(),
                    "source_name": source["name"],
                    "source_url": source["url"],
                    "category": (semantics.get("category") or {}).get("id"),
                    "confidence": semantics.get("confidence"),
                    "score": semantics.get("score"),
                    "margin": signals["margin"],
                    "reasons": signals["reasons"],
                    "candidates": signals["candidates"],
                    "evidence": semantics.get("evidence", []),
                }
            )

    public_sources: dict[str, dict[str, Any]] = {}
    for key, bucket in sorted(sources.items()):
        classified = int(bucket["classified_events"])
        public_sources[key] = {
            **bucket,
            "low_confidence_rate": _rate(int(bucket["low_confidence_count"]), classified),
            "narrow_margin_rate": _rate(int(bucket["narrow_margin_count"]), classified),
            "uncertain_rate": _rate(int(bucket["uncertain_count"]), classified),
        }

    queue.sort(
        key=lambda row: (
            0 if "low_confidence" in row["reasons"] else 1,
            float(row["margin"]) if row["margin"] is not None else 1e9,
            row["city_id"],
            row["source_name"],
            row["title"],
        )
    )
    return {
        "summary": {
            "total_events": total_events,
            "classified_events": classified_events,
            "low_confidence_count": low_confidence_count,
            "low_confidence_rate": _rate(low_confidence_count, classified_events),
            "narrow_margin_count": narrow_margin_count,
            "narrow_margin_rate": _rate(narrow_margin_count, classified_events),
            "uncertain_count": uncertain_count,
            "uncertain_rate": _rate(uncertain_count, classified_events),
        },
        "source_metrics": public_sources,
        "review_queue": queue,
    }


def detect_uncertainty_anomalies(
    current: dict[str, Any],
    baseline: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    baseline_sources = (baseline or {}).get("source_metrics", {})

    for key, now in current.get("source_metrics", {}).items():
        classified = int(now.get("classified_events", 0))
        if classified < MINIMUM_EVENTS_FOR_SOURCE_RISK:
            continue
        rate = float(now.get("uncertain_rate", 0.0))
        before = baseline_sources.get(key)

        if rate >= UNCERTAIN_RATE_WARNING:
            severity = "critical" if rate >= UNCERTAIN_RATE_CRITICAL else "warning"
            if before is None or int(before.get("classified_events", 0)) < MINIMUM_EVENTS_FOR_SOURCE_RISK:
                anomalies.append(
                    {
                        "type": "high_uncertainty_rate",
                        "severity": severity,
                        "source_key": key,
                        "city_id": now.get("city_id"),
                        "source_name": now.get("source_name"),
                        "current_rate": rate,
                    }
                )
            else:
                old_rate = float(before.get("uncertain_rate", 0.0))
                delta = rate - old_rate
                if delta >= UNCERTAIN_RATE_DELTA_WARNING:
                    anomalies.append(
                        {
                            "type": "uncertainty_rate_spike",
                            "severity": severity,
                            "source_key": key,
                            "city_id": now.get("city_id"),
                            "source_name": now.get("source_name"),
                            "baseline_rate": old_rate,
                            "current_rate": rate,
                            "delta": round(delta, 6),
                        }
                    )
                elif rate >= UNCERTAIN_RATE_CRITICAL:
                    anomalies.append(
                        {
                            "type": "persistently_high_uncertainty_rate",
                            "severity": "critical",
                            "source_key": key,
                            "city_id": now.get("city_id"),
                            "source_name": now.get("source_name"),
                            "baseline_rate": old_rate,
                            "current_rate": rate,
                        }
                    )

    return sorted(
        anomalies,
        key=lambda row: (
            0 if row["severity"] == "critical" else 1,
            -float(row.get("current_rate", 0.0)),
            str(row.get("city_id") or ""),
            str(row.get("source_name") or ""),
        ),
    )


def build_report(compare_ref: str | None = None) -> dict[str, Any]:
    current = build_uncertainty_snapshot(load_city_events())
    baseline = None
    baseline_error = None
    if compare_ref:
        try:
            baseline = build_uncertainty_snapshot(load_city_events(compare_ref))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            baseline_error = str(exc)

    anomalies = detect_uncertainty_anomalies(current, baseline)
    return {
        "schema_version": "1.0.0",
        "diagnostic_policy": {
            "narrow_margin_points": NARROW_MARGIN_POINTS,
            "low_confidence_values": sorted(LOW_CONFIDENCE_VALUES),
            "minimum_events_for_source_risk": MINIMUM_EVENTS_FOR_SOURCE_RISK,
            "uncertain_rate_warning": UNCERTAIN_RATE_WARNING,
            "uncertain_rate_critical": UNCERTAIN_RATE_CRITICAL,
            "uncertain_rate_delta_warning": UNCERTAIN_RATE_DELTA_WARNING,
            "mutates_classification": False,
        },
        "compare_ref": compare_ref,
        "baseline_error": baseline_error,
        "summary": {
            **current["summary"],
            "source_count": len(current["source_metrics"]),
            "source_risk_count": len(anomalies),
            "critical_source_risk_count": sum(1 for row in anomalies if row["severity"] == "critical"),
        },
        "review_queue": current["review_queue"],
        "source_metrics": current["source_metrics"],
        "source_risks": anomalies,
    }


def _escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any], queue_limit: int = 50) -> str:
    summary = report["summary"]
    lines = [
        "# Diagnóstico de incertidumbre de clasificación",
        "",
        (
            f"Eventos clasificados: **{summary['classified_events']}** · "
            f"confianza baja: **{summary['low_confidence_count']}** "
            f"({summary['low_confidence_rate']:.1%}) · "
            f"margen estrecho: **{summary['narrow_margin_count']}** "
            f"({summary['narrow_margin_rate']:.1%}) · "
            f"a revisar: **{summary['uncertain_count']}** "
            f"({summary['uncertain_rate']:.1%})."
        ),
        (
            f"Fuentes con riesgo: **{summary['source_risk_count']}** · "
            f"críticas: **{summary['critical_source_risk_count']}**."
        ),
        "",
        "> Este diagnóstico es de solo lectura: nunca cambia una categoría automáticamente.",
        "",
        "## Cola de revisión",
        "",
    ]

    queue = report.get("review_queue", [])[:queue_limit]
    if not queue:
        lines.append("No hay clasificaciones con confianza baja ni candidatos demasiado próximos.")
    else:
        lines.extend(
            [
                "| Ciudad | Fuente | Evento | Categoría | Motivo | Margen | Candidatos |",
                "| --- | --- | --- | --- | --- | ---: | --- |",
            ]
        )
        for row in queue:
            candidates = ", ".join(
                f"{candidate.get('category')} ({candidate.get('score'):g})"
                for candidate in row.get("candidates", [])[:3]
            ) or "—"
            margin = "—" if row.get("margin") is None else f"{float(row['margin']):g}"
            lines.append(
                f"| {_escape(row.get('city_id'))} | {_escape(row.get('source_name'))} | "
                f"{_escape(row.get('title'))} | {_escape(row.get('category'))} | "
                f"{_escape(', '.join(row.get('reasons', [])))} | {margin} | {_escape(candidates)} |"
            )
        if len(report.get("review_queue", [])) > queue_limit:
            lines.append(
                f"\n_Mostrando {queue_limit} de {len(report['review_queue'])}; el JSON conserva la cola completa._"
            )

    lines.extend(["", "## Fuentes con riesgo de clasificación", ""])
    risks = report.get("source_risks", [])
    if not risks:
        lines.append("No se detectan fuentes con una tasa de incertidumbre relevante.")
    else:
        lines.extend(
            [
                "| Severidad | Ciudad | Fuente | Riesgo | Tasa actual |",
                "| --- | --- | --- | --- | ---: |",
            ]
        )
        for row in risks:
            lines.append(
                f"| {_escape(row.get('severity'))} | {_escape(row.get('city_id'))} | "
                f"{_escape(row.get('source_name'))} | {_escape(row.get('type'))} | "
                f"{float(row.get('current_rate', 0.0)):.1%} |"
            )

    if report.get("baseline_error"):
        lines.extend(["", f"Baseline no disponible: `{_escape(report['baseline_error'])}`"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit low-confidence and narrow-margin public classifications.")
    parser.add_argument("--compare-ref", default=None)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--markdown-output", default=None)
    parser.add_argument("--queue-limit", type=int, default=50)
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()

    report = build_report(args.compare_ref)
    if args.json_output:
        path = ROOT / args.json_output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        path = ROOT / args.markdown_output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report, args.queue_limit), encoding="utf-8")

    summary = report["summary"]
    print(
        "CLASSIFICATION_UNCERTAINTY "
        f"classified={summary['classified_events']} "
        f"low_confidence={summary['low_confidence_count']} "
        f"narrow_margin={summary['narrow_margin_count']} "
        f"uncertain={summary['uncertain_count']} "
        f"source_risks={summary['source_risk_count']} "
        f"critical={summary['critical_source_risk_count']}"
    )
    if args.fail_on_critical and summary["critical_source_risk_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
