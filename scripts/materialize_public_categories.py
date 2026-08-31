from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.public_category_rules import (
    CATEGORIES,
    FALLBACK_ID,
    canonical_public_category,
    classify_public_category,
    is_thematic_category,
    source_category,
)
from app.scripts.apply_content_quality_guard import materialize_submission_call, non_event_context_reason
from app.scripts.transformation_receipt_ledger import (
    append_receipt,
    load_ledger,
    make_receipt,
    semantic_payload,
    write_ledger,
)

DEFAULT_DATASETS = (ROOT / "agenda_web.json", ROOT / "app/data/gijon/agenda_web.json")
CONTRACT_VERSION = "shared-canonical-category-migration-v1"
DEFAULT_LEDGER = ROOT / "app/data/quality/transformation-receipts.json"
PROGRAM_SHELL_TITLE = re.compile(r"\b(?:programaci[oó]n|cartelera|agenda|inscripciones?)\b", re.I)


def normalize_publication_metadata(payload: dict) -> bool:
    """Keep publication_date derived from generated_at in the dataset timezone.

    Semantic/materialization passes must not pretend that a dataset was freshly
    ingested, so generated_at is preserved. They may, however, repair stale or
    inconsistent publication_date metadata deterministically from that timestamp.
    """

    generated_raw = str(payload.get("generated_at") or "").strip()
    timezone_name = str(payload.get("timezone") or "").strip()
    if not generated_raw or not timezone_name:
        return False

    generated = datetime.fromisoformat(generated_raw.replace("Z", "+00:00"))
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=ZoneInfo(timezone_name))
    expected = generated.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    if payload.get("publication_date") == expected:
        return False
    payload["publication_date"] = expected
    return True


def _official_evidence_url(event: dict) -> str | None:
    links = event.get("links") if isinstance(event.get("links"), dict) else {}
    return links.get("official") or event.get("source_url") or links.get("source")


def _future_publicable_event(event: dict, publication_date: str) -> bool:
    event_type = str(event.get("event_type") or "event")
    if event_type == "program" and _verified_program_shell(event):
        return False
    if event_type not in {"event", "program"}:
        return False
    schedule = event.get("schedule") if isinstance(event.get("schedule"), dict) else {}
    final_day = str(schedule.get("end") or schedule.get("start") or "")[:10]
    return bool(publication_date and final_day and final_day >= publication_date)


def _verified_program_shell(event: dict) -> bool:
    """Require structural program evidence; event_type alone is not an escape hatch."""
    if str(event.get("event_type") or "") != "program":
        return False
    schedule = event.get("schedule") if isinstance(event.get("schedule"), dict) else {}
    editorial = event.get("editorial") if isinstance(event.get("editorial"), dict) else {}
    title_signal = bool(PROGRAM_SHELL_TITLE.search(str(event.get("title") or "")))
    structured_signal = editorial.get("classification") == "program"
    return schedule.get("mode") == "multi_day" and (title_signal or structured_signal)


def _historical_legacy_inventory_scope(event: dict, payload: dict) -> bool:
    """Identify the previously reported 16 Valpo + 21 Gijón legacy rows.

    This is diagnostic only.  Enforcement remains taxonomy-driven and does not
    use a city/source allow-list.
    """
    if not _future_publicable_event(event, str(payload.get("publication_date") or "")):
        return False
    category_id = str((event.get("primary_category") or {}).get("id") or "").strip().casefold()
    timezone_name = str(payload.get("timezone") or "")
    if timezone_name == "America/Santiago":
        return category_id == "otros"
    if timezone_name == "Europe/Madrid":
        return category_id in {"actividad-panorama", "cultura"}
    return False


def migrate_payload(
    payload: dict,
    *,
    ledger: dict | None = None,
    generated_at: str | None = None,
) -> tuple[dict, dict]:
    """Converge source taxonomies to the shared public taxonomy without guessing.

    Already thematic categories are preserved (and registered aliases are
    normalized).  Legacy/fallback categories are reclassified only when the
    shared evidence classifier reaches its minimum score.  Unresolved rows stay
    unchanged and are reported as blockers, making retries idempotent.
    """
    migrated = copy.deepcopy(payload)
    inventory: list[dict] = []
    actions = ("preserved", "normalized", "reclassified", "excluded", "blocked")
    counts = dict.fromkeys(actions, 0)
    audited_counts = dict.fromkeys(actions, 0)
    historical_counts = dict.fromkeys(actions, 0)
    publication_date = str(migrated.get("publication_date") or "")
    retained_events: list[dict] = []
    for event in migrated.get("events") or []:
        materialize_submission_call(event)
        current = source_category(event)
        canonical = canonical_public_category(current)
        classification = classify_public_category(event)
        evidence = classification.get("evidence") or []

        exclusion_reason = non_event_context_reason(event)
        if exclusion_reason:
            proposed = dict(current)
            action = "excluded"
        elif canonical and is_thematic_category(canonical.get("id")):
            proposed = dict(canonical)
            exact = event.get("primary_category") == proposed and event.get("categories") == [proposed]
            action = "preserved" if exact else "normalized"
        elif classification["category"]["id"] != FALLBACK_ID:
            proposed = dict(classification["category"])
            action = "reclassified"
        elif _future_publicable_event(event, publication_date):
            proposed = dict(classification["category"])
            action = "blocked"
        else:
            proposed = dict(current)
            action = "preserved"

        counts[action] += 1
        in_strict_scope = _future_publicable_event(event, publication_date) and not (
            canonical and is_thematic_category(canonical.get("id"))
        )
        if in_strict_scope:
            audited_counts[action] += 1
        in_historical_scope = _historical_legacy_inventory_scope(event, migrated)
        if in_historical_scope:
            historical_counts[action] += 1
        inventory.append({
            "id": event.get("id"),
            "city": (event.get("location") or {}).get("city"),
            "source": event.get("source_id") or event.get("source_name"),
            "title": event.get("title"),
            "current_category": current,
            "official_evidence": {
                "url": _official_evidence_url(event),
                "signals": evidence,
            },
            "proposed_category": proposed,
            "confidence": classification.get("confidence"),
            "score": classification.get("score", 0),
            "action": action,
            "action_reason": exclusion_reason,
            "strict_gate_scope": in_strict_scope,
            "historical_37_scope": in_historical_scope,
        })
        if action == "excluded":
            if ledger is not None:
                receipt_action = "non_event_exclusion" if exclusion_reason == "promotional_giveaway_not_attendance_event" else "quarantine"
                append_receipt(ledger, make_receipt(
                    stage="canonical_category_materializer",
                    action=receipt_action,
                    reason=str(exclusion_reason),
                    source_event=event,
                    canonical_event_id=None,
                    destination={"state": receipt_action, "canonical_event_id": None},
                    evidence={"classification": classification},
                ))
            continue
        retained_events.append(event)
        if action == "blocked":
            continue
        event["primary_category"] = proposed
        event["categories"] = [proposed]
        if ledger is not None and action in {"normalized", "reclassified"}:
            append_receipt(ledger, make_receipt(
                stage="canonical_category_materializer",
                action="reclassification",
                reason=f"canonical_category_{action}",
                source_event=event,
                canonical_event_id=str(event.get("id") or ""),
                destination={"state": "published", "canonical_event_id": event.get("id"), "category": proposed},
                evidence={"classification": classification, "previous_category": current},
            ))
        semantics = event.get("semantics")
        if isinstance(semantics, dict) and "canonical_category" in semantics:
            semantics["canonical_category"] = proposed

    migrated["events"] = retained_events
    if semantic_payload(migrated) != semantic_payload(payload):
        migrated["generated_at"] = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
        if ledger is not None:
            ledger["generated_at"] = migrated["generated_at"]

    report = {
        "contract": CONTRACT_VERSION,
        "canonical_taxonomy": sorted(
            category_id for category_id, spec in CATEGORIES.items() if spec.get("thematic")
        ),
        "fallback_category": FALLBACK_ID,
        "counts": counts,
        "audited_legacy_future_events": audited_counts,
        "historical_37_inventory": historical_counts,
        "inventory": inventory,
    }
    return migrated, report


def materialize(
    path: Path,
    *,
    report_path: Path | None = None,
    require_classified: bool = False,
    ledger: dict | None = None,
    generated_at: str | None = None,
) -> tuple[int, int, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalize_publication_metadata(payload)
    migrated, report = migrate_payload(payload, ledger=ledger, generated_at=generated_at)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
    blockers = report["counts"]["blocked"]
    if require_classified and blockers:
        raise ValueError(f"PUBLIC_CATEGORY_MIGRATION_BLOCKED count={blockers}")
    changed = sum(1 for before, after in zip(payload.get("events") or [], migrated.get("events") or []) if before != after)
    if migrated != payload:
        path.write_text(
            json.dumps(migrated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
    return len(migrated.get("events") or []), changed, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize the shared semantic public category into city datasets.")
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--require-classified", action="store_true")
    parser.add_argument("--contract", choices=[CONTRACT_VERSION])
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--generated-at")
    args = parser.parse_args()
    paths = args.paths or list(DEFAULT_DATASETS)
    ledger = load_ledger(args.ledger)
    prepared: list[tuple[Path, dict, dict, dict, Path | None]] = []
    for raw in paths:
        path = raw if raw.is_absolute() else ROOT / raw
        payload = json.loads(path.read_text(encoding="utf-8"))
        normalize_publication_metadata(payload)
        migrated, report = migrate_payload(payload, ledger=ledger, generated_at=args.generated_at)
        report_path = args.report_dir / f"{path.stem}-{path.parent.name}.json" if args.report_dir else None
        prepared.append((path, payload, migrated, report, report_path))

    for _path, _payload, _migrated, report, report_path in prepared:
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

    blockers = sum(item[3]["counts"]["blocked"] for item in prepared)
    if args.require_classified and blockers:
        print(f"PUBLIC_CATEGORY_MIGRATION_BLOCKED count={blockers}", file=sys.stderr)
        return 1

    for path, payload, migrated, report, _report_path in prepared:
        total = len(migrated.get("events") or [])
        changed = sum(1 for before, after in zip(payload.get("events") or [], migrated.get("events") or []) if before != after)
        if migrated != payload:
            path.write_text(
                json.dumps(migrated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8", newline="\n",
            )
        counts = report["counts"]
        display_path = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(
            f"PUBLIC_CATEGORIES_MATERIALIZED path={display_path} total={total} changed={changed} "
            f"preserved={counts['preserved']} normalized={counts['normalized']} "
            f"reclassified={counts['reclassified']} blocked={counts['blocked']}"
        )
    write_ledger(args.ledger, ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
