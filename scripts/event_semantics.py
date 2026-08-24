from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.public_category_rules import classify_public_category, fold

ROOT = Path(__file__).resolve().parents[1]
SEMANTICS_PATH = ROOT / "shared" / "event-semantics.json"
EVENT_KIND_PATH = ROOT / "shared" / "event-diagnostic-semantics.json"
EVENT_SEMANTICS = json.loads(SEMANTICS_PATH.read_text(encoding="utf-8"))
EVENT_KIND_SEMANTICS = json.loads(EVENT_KIND_PATH.read_text(encoding="utf-8"))
SEMANTIC_EVIDENCE_KINDS = set(
    EVENT_SEMANTICS["secondary_domain"].get("semantic_evidence_kinds", [])
)


def _compile_dimension_rules(spec: dict[str, Any]) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    for rule in sorted(
        spec.get("rules", []),
        key=lambda item: -int(item.get("priority", 0)),
    ):
        compiled.append(
            {
                **rule,
                "regexes": [re.compile(pattern) for pattern in rule.get("patterns", [])],
            }
        )
    return compiled


FORMAT_RULES = _compile_dimension_rules(EVENT_SEMANTICS["format"])
AUDIENCE_RULES = _compile_dimension_rules(EVENT_SEMANTICS["audience"])
EVENT_KIND_PROGRAM_RE = [
    re.compile(pattern)
    for pattern in EVENT_KIND_SEMANTICS.get("event_kind", {}).get("program_title_patterns", [])
]
EVENT_KIND_EVENT_RE = [
    re.compile(pattern)
    for pattern in EVENT_KIND_SEMANTICS.get("event_kind", {}).get("event_title_patterns", [])
]


def _text_for_scope(event: dict[str, Any], scope: str) -> str:
    if scope == "title":
        return fold(event.get("title"))
    values = [event.get("description"), *(event.get("tags") or [])]
    return fold(" ".join(str(value) for value in values if value))


def _match_dimension(
    event: dict[str, Any],
    spec: dict[str, Any],
    compiled_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    for scope in ("title", "description"):
        text = _text_for_scope(event, scope)
        if not text:
            continue
        for rule in compiled_rules:
            matched = next(
                (pattern for pattern in rule["regexes"] if pattern.search(text)),
                None,
            )
            if matched is None:
                continue
            value = rule.get("value") or spec["fallback"]
            return {
                "value": value,
                "label": spec.get("values", {}).get(value, {}).get("label", value),
                "confidence": "high" if scope == "title" else "medium",
                "evidence": [
                    {
                        "rule": rule["id"],
                        "scope": scope,
                        "pattern": matched.pattern,
                        "priority": int(rule.get("priority", 0)),
                    }
                ],
            }

    value = spec["fallback"]
    return {
        "value": value,
        "label": spec.get("values", {}).get(value, {}).get("label", value),
        "confidence": "unspecified",
        "evidence": [],
    }


def _lifecycle_value(event: dict[str, Any]) -> dict[str, Any]:
    lifecycle = event.get("lifecycle")
    if isinstance(lifecycle, str) and lifecycle.strip():
        return {"value": lifecycle.strip(), "source": "lifecycle"}
    if isinstance(lifecycle, dict):
        for key in ("state", "kind", "type", "value"):
            value = str(lifecycle.get(key) or "").strip()
            if value:
                return {"value": value, "source": f"lifecycle.{key}"}

    content_kind = str(event.get("content_kind") or "").strip()
    if content_kind:
        return {"value": content_kind, "source": "content_kind"}
    return {
        "value": EVENT_SEMANTICS["lifecycle"]["fallback"],
        "source": None,
    }


def _event_kind_value(event: dict[str, Any]) -> dict[str, Any]:
    spec = EVENT_KIND_SEMANTICS.get("event_kind", {})
    event_type = fold(event.get("event_type"))
    program_types = {fold(value) for value in spec.get("program_event_types", [])}
    if event_type and event_type in program_types:
        return {"value": "program", "source": "event_type", "evidence": event_type}

    title = fold(event.get("title"))
    for pattern in EVENT_KIND_PROGRAM_RE:
        if pattern.search(title):
            return {"value": "program", "source": "title", "evidence": pattern.pattern}
    for pattern in EVENT_KIND_EVENT_RE:
        if pattern.search(title):
            return {"value": "event", "source": "title", "evidence": pattern.pattern}
    return {"value": spec.get("fallback", "event"), "source": None, "evidence": None}


def _diagnostic_eligibility(event: dict[str, Any], event_kind: str) -> dict[str, Any]:
    spec = EVENT_KIND_SEMANTICS.get("diagnostic", {})
    event_type = fold(event.get("event_type"))
    excluded_types = {fold(value) for value in spec.get("excluded_event_types", [])}
    if event_type and event_type in excluded_types:
        return {"eligible": False, "reason": f"event_type:{event_type}"}
    if event_kind in set(spec.get("excluded_event_kinds", [])):
        return {"eligible": False, "reason": f"event_kind:{event_kind}"}
    for flag in spec.get("excluded_flags", []):
        if event.get(flag) is True:
            return {"eligible": False, "reason": f"flag:{flag}"}
    return {"eligible": True, "reason": None}


def _secondary_domains(classification: dict[str, Any]) -> list[str]:
    primary_id = (classification.get("category") or {}).get("id")
    if not primary_id or primary_id == "unclassified":
        return []

    spec = EVENT_SEMANTICS["secondary_domain"]
    threshold = max(
        float(spec.get("minimum_score", 0)),
        float(classification.get("score", 0)) * float(spec.get("minimum_ratio_to_primary", 0)),
    )
    require_semantic_evidence = bool(spec.get("require_semantic_evidence"))

    secondary: list[str] = []
    for candidate in classification.get("candidates", []):
        category_id = (candidate.get("category") or {}).get("id")
        if not category_id or category_id == primary_id:
            continue
        if float(candidate.get("score", 0)) < threshold:
            continue
        if require_semantic_evidence and not any(
            item.get("kind") in SEMANTIC_EVIDENCE_KINDS
            for item in candidate.get("evidence", [])
        ):
            continue
        secondary.append(category_id)
    return secondary


def classify_event_format(event: dict[str, Any]) -> dict[str, Any]:
    return _match_dimension(event, EVENT_SEMANTICS["format"], FORMAT_RULES)


def classify_event_audience(event: dict[str, Any]) -> dict[str, Any]:
    return _match_dimension(event, EVENT_SEMANTICS["audience"], AUDIENCE_RULES)


def build_event_semantics(event: dict[str, Any] | None = None) -> dict[str, Any]:
    event = event or {}
    classification = classify_public_category(event)
    event_format = classify_event_format(event)
    audience = classify_event_audience(event)
    lifecycle = _lifecycle_value(event)
    event_kind = _event_kind_value(event)
    diagnostic = _diagnostic_eligibility(event, event_kind["value"])
    primary_domain = (
        None
        if classification["category"]["id"] == "unclassified"
        else classification["category"]["id"]
    )

    return {
        "schema_version": EVENT_SEMANTICS["schema_version"],
        "category": classification["category"],
        "classification_state": "classified" if primary_domain else "unclassified",
        "primary_domain": primary_domain,
        "secondary_domains": _secondary_domains(classification),
        "confidence": classification["confidence"],
        "score": classification["score"],
        "evidence": classification["evidence"],
        "domain_candidates": classification.get("candidates", []),
        "source_category": classification["source_category"],
        "format": event_format["value"],
        "audience": audience["value"],
        "lifecycle": lifecycle["value"],
        "event_kind": event_kind["value"],
        "diagnostic_eligible": diagnostic["eligible"],
        "diagnostic_exclusion_reason": diagnostic["reason"],
        "trace": {
            "format": event_format,
            "audience": audience,
            "lifecycle": lifecycle,
            "event_kind": event_kind,
            "diagnostic": diagnostic,
        },
    }


def annotate_event_semantics(event: dict[str, Any]) -> dict[str, Any]:
    return {
        **event,
        "semantics": build_event_semantics(event),
    }
