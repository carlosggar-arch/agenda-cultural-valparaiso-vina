from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

SCHEMA_VERSION = "1.0.0"
CONTRACT = "canonical-transformation-receipt-ledger"


def _text(value: Any) -> str:
    return str(value or "").strip()


def source_url(event: dict[str, Any]) -> str:
    links = event.get("links") if isinstance(event.get("links"), dict) else {}
    return _text(event.get("source_url") or links.get("official") or links.get("source"))


def occurrence_id(event: dict[str, Any], occurrence: dict[str, Any] | None = None) -> str:
    url = source_url(event)
    try:
        explicit = (parse_qs(urlparse(url).query).get("occurrence") or [""])[0]
    except ValueError:
        explicit = ""
    schedule = occurrence or (event.get("schedule") if isinstance(event.get("schedule"), dict) else {})
    identity = {
        "explicit": explicit,
        "start": schedule.get("start"),
        "end": schedule.get("end"),
        "venue": (event.get("location") or {}).get("venue_id") or (event.get("location") or {}).get("venue"),
    }
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    return f"occurrence:{explicit or digest}"


def empty_ledger(*, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": CONTRACT,
        "generated_at": generated_at,
        "receipts": [],
    }


def load_ledger(path: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        return empty_ledger(generated_at=generated_at)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("contract") != CONTRACT:
        raise ValueError(f"Invalid transformation receipt ledger: {path}")
    if not isinstance(payload.get("receipts"), list):
        raise ValueError(f"Invalid transformation receipt rows: {path}")
    return payload


def make_receipt(
    *,
    stage: str,
    action: str,
    reason: str,
    source_event: dict[str, Any],
    canonical_event_id: str | None = None,
    destination: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    preserved_fields: list[str] | None = None,
    combined_provenance: Any = None,
    occurrence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_id = _text(source_event.get("id"))
    result_id = _text(canonical_event_id) or source_id
    receipt = {
        "stage": _text(stage),
        "action": _text(action),
        "reason": _text(reason),
        "source_record_id": source_id,
        "canonical_event_id": result_id or None,
        "occurrence_id": occurrence_id(source_event, occurrence),
        "source_url": source_url(source_event) or None,
        "title": source_event.get("title"),
        "provenance": copy.deepcopy(source_event.get("provenance") or {
            "source_url": source_url(source_event),
            "method": "source_record_provenance",
        }),
        "destination": copy.deepcopy(destination or {"state": action, "canonical_event_id": result_id or None}),
    }
    if evidence:
        receipt["evidence"] = copy.deepcopy(evidence)
    if preserved_fields is not None:
        receipt["preserved_fields"] = sorted(set(preserved_fields))
    if combined_provenance is not None:
        receipt["combined_provenance"] = copy.deepcopy(combined_provenance)
    return receipt


def receipt_identity(receipt: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_text(receipt.get(key)) for key in (
        "stage", "action", "reason", "source_record_id", "canonical_event_id", "occurrence_id"
    ))


def append_receipt(ledger: dict[str, Any], receipt: dict[str, Any]) -> bool:
    identity = receipt_identity(receipt)
    rows = ledger.setdefault("receipts", [])
    if any(receipt_identity(existing) == identity for existing in rows):
        return False
    rows.append(copy.deepcopy(receipt))
    rows.sort(key=receipt_identity)
    return True


def semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result.pop("generated_at", None)
    return result


def write_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
