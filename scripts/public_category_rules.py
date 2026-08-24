from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT / "shared" / "public-category-taxonomy.json"
TAXONOMY = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
CATEGORIES: dict[str, dict[str, Any]] = TAXONOMY["categories"]
ALIASES: dict[str, str] = TAXONOMY["aliases"]
LABEL_ALIASES: dict[str, str] = TAXONOMY["label_aliases"]
GROUPS: dict[str, list[str]] = TAXONOMY["groups"]
RULES = TAXONOMY["rules"]
FALLBACK_ID = TAXONOMY["fallback_category"]
CATEGORY_ORDER = {
    category_id: index
    for index, category_id in enumerate(TAXONOMY.get("category_order", CATEGORIES.keys()))
}
SUMMER_PROGRAM_EVENT_TYPES = set(RULES["summer_program_event_types"])
SUMMER_PROGRAM_RE = re.compile(RULES["summer_program_title_pattern"])
SUMMER_REGISTRATION_RE = re.compile(RULES["summer_registration_title_pattern"])
TITLE_EVIDENCE_RULES = [
    (rule["category"], int(rule["weight"]), re.compile(rule["pattern"]))
    for rule in RULES["title_evidence"]
]
DESCRIPTION_EVIDENCE_RULES = [
    (rule["category"], int(rule["weight"]), re.compile(rule["pattern"]))
    for rule in RULES["description_evidence"]
]
SOURCE_EVIDENCE_RULES = [
    (rule["category"], int(rule["weight"]), re.compile(rule["pattern"]))
    for rule in RULES.get("source_evidence", [])
]
SOURCE_TITLE_EVIDENCE_RULES = [
    {**rule, "weight": int(rule["weight"]), "regex": re.compile(rule["pattern"])}
    for rule in RULES.get("source_title_evidence", [])
]
SEMANTIC_NOISE_FIELDS = tuple(RULES.get("semantic_noise_fields", []))
SEMANTIC_NOISE_PHRASES = tuple(RULES.get("semantic_noise_phrases", []))


def fold(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def source_category(event: dict[str, Any]) -> dict[str, str]:
    source = (
        (event.get("semantics") or {}).get("source_category")
        or event.get("primary_category")
        or (event.get("categories") or [None])[0]
        or {}
    )
    label = str(source.get("label") or "").strip()
    category_id = str(source.get("id") or re.sub(r"\s+", "-", fold(label))).strip().casefold()
    return {"id": category_id, "label": label}


def canonical_public_category(category: dict[str, Any] | str | None) -> dict[str, str] | None:
    raw = {"id": category, "label": ""} if isinstance(category, str) else (category or {})
    label = str(raw.get("label") or "").strip()
    category_id = str(raw.get("id") or re.sub(r"\s+", "-", fold(label))).strip().casefold()
    canonical_id = ALIASES.get(category_id) or LABEL_ALIASES.get(fold(label))
    if not canonical_id and category_id in CATEGORIES:
        canonical_id = category_id
    if canonical_id:
        return {"id": canonical_id, "label": CATEGORIES[canonical_id]["label"]}
    if category_id or label:
        return {"id": category_id, "label": label or category_id}
    return None


def canonical_public_category_id(category: dict[str, Any] | str | None) -> str | None:
    resolved = canonical_public_category(category)
    return resolved.get("id") if resolved else None


def is_public_category_in_group(category: dict[str, Any] | str | None, group_name: str) -> bool:
    category_id = canonical_public_category_id(category)
    return bool(category_id and category_id in GROUPS.get(group_name, []))


def category(category_id: str) -> dict[str, str]:
    resolved_id = category_id if category_id in CATEGORIES else FALLBACK_ID
    return {"id": resolved_id, "label": CATEGORIES[resolved_id]["label"]}


def is_thematic_category(category_id: str | None) -> bool:
    return bool(category_id and CATEGORIES.get(category_id, {}).get("thematic") is True)


def is_summer_program(event: dict[str, Any]) -> bool:
    if str(event.get("event_type") or "") not in SUMMER_PROGRAM_EVENT_TYPES:
        return False
    title = fold(event.get("title"))
    return bool(SUMMER_PROGRAM_RE.search(title) or SUMMER_REGISTRATION_RE.search(title))


def _scalar_noise_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            str(value.get(key) or "")
            for key in ("name", "label", "title", "address", "city", "venue")
            if value.get(key)
        ]
    return []


def _semantic_noise_values(event: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for field in SEMANTIC_NOISE_FIELDS:
        values.extend(_scalar_noise_values(event.get(field)))
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    values.extend(_scalar_noise_values(source.get("name")))
    return [fold(value) for value in values if len(fold(value)) >= 4]


def _strip_semantic_noise(text: str, event: dict[str, Any]) -> str:
    cleaned = fold(text)
    for phrase in SEMANTIC_NOISE_PHRASES:
        token = fold(phrase)
        if token:
            cleaned = re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", " ", cleaned)
    for token in sorted(set(_semantic_noise_values(event)), key=len, reverse=True):
        cleaned = re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def description_evidence_text(event: dict[str, Any]) -> str:
    values = [event.get("description"), *(event.get("tags") or [])]
    return _strip_semantic_noise(
        " ".join(str(value) for value in values if value),
        event,
    )


def source_evidence_text(event: dict[str, Any]) -> str:
    # Kept as a compatibility helper. Generic source/organizer text is no longer
    # semantic category evidence; source-specific evidence must be declarative.
    return ""


def _add_evidence(
    scores: dict[str, int],
    evidence: list[dict[str, Any]],
    category_id: str,
    weight: int,
    kind: str,
    value: Any,
) -> None:
    if not is_thematic_category(category_id) or not weight:
        return
    scores[category_id] = scores.get(category_id, 0) + weight
    evidence.append(
        {"category": category_id, "weight": weight, "kind": kind, "value": value}
    )


def _add_rule_evidence(
    scores: dict[str, int],
    evidence: list[dict[str, Any]],
    text: str,
    rules: list[tuple[str, int, re.Pattern[str]]],
    kind: str,
) -> None:
    if not text:
        return
    for category_id, weight, pattern in rules:
        if pattern.search(text):
            _add_evidence(scores, evidence, category_id, weight, kind, pattern.pattern)


def _add_source_title_evidence(
    scores: dict[str, int],
    evidence: list[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    title = fold(event.get("title"))
    source_id = str(event.get("source_id") or "").strip()
    if not title or not source_id:
        return
    for rule in SOURCE_TITLE_EVIDENCE_RULES:
        if str(rule.get("source_id") or "") != source_id:
            continue
        if rule["regex"].search(title):
            _add_evidence(
                scores,
                evidence,
                str(rule["category"]),
                int(rule["weight"]),
                "source_title",
                rule.get("reason") or rule["pattern"],
            )


def _confidence_for_score(score: int) -> str:
    if score >= 120:
        return "high"
    if score >= 70:
        return "medium"
    if score >= int(RULES.get("minimum_score", 1)):
        return "low"
    return "unclassified"


def _ranked_candidates(
    scores: dict[str, int], evidence: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ranked = sorted(
        ((category_id, score) for category_id, score in scores.items() if score > 0),
        key=lambda item: (-item[1], CATEGORY_ORDER.get(item[0], 10_000)),
    )
    return [
        {
            "category": category(category_id),
            "score": score,
            "confidence": _confidence_for_score(score),
            "evidence": [item for item in evidence if item.get("category") == category_id],
        }
        for category_id, score in ranked
    ]


def classify_public_category(event: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, int] = {}
    evidence: list[dict[str, Any]] = []
    source = source_category(event)
    canonical_source = canonical_public_category(source)
    recovery_hint = canonical_public_category(
        (event.get("editorial") or {}).get("category_recovery_hint")
    )

    if is_summer_program(event):
        _add_evidence(
            scores, evidence, "cursos-talleres-campus", 180, "event_type", "summer_program"
        )

    if canonical_source and is_thematic_category(canonical_source.get("id")):
        _add_evidence(
            scores,
            evidence,
            canonical_source["id"],
            int(RULES.get("source_category_weight", 0)),
            "source_category",
            source.get("id") or source.get("label"),
        )

    if recovery_hint and is_thematic_category(recovery_hint.get("id")):
        _add_evidence(
            scores,
            evidence,
            recovery_hint["id"],
            int(RULES.get("recovery_hint_weight", RULES.get("source_category_weight", 0))),
            "recovery_hint",
            (event.get("editorial") or {}).get("category_recovery_hint"),
        )

    # Generic venue/organizer/source-name text is intentionally excluded.
    # Verified sparse-title exceptions remain declarative in source_title_evidence.
    _add_source_title_evidence(scores, evidence, event)
    _add_rule_evidence(
        scores, evidence, fold(event.get("title")), TITLE_EVIDENCE_RULES, "title"
    )
    _add_rule_evidence(
        scores, evidence, description_evidence_text(event), DESCRIPTION_EVIDENCE_RULES, "description"
    )

    candidates = _ranked_candidates(scores, evidence)
    minimum_score = int(RULES.get("minimum_score", 1))
    winner = next(
        (candidate for candidate in candidates if candidate["score"] >= minimum_score),
        None,
    )

    if not winner:
        return {
            "category": category(FALLBACK_ID),
            "confidence": "unclassified",
            "score": candidates[0]["score"] if candidates else 0,
            "evidence": evidence,
            "source_category": source,
            "candidates": candidates,
        }

    return {
        "category": winner["category"],
        "confidence": winner["confidence"],
        "score": winner["score"],
        "evidence": evidence,
        "source_category": source,
        "candidates": candidates,
    }


def resolve_public_category(event: dict[str, Any]) -> dict[str, str]:
    return dict(classify_public_category(event)["category"])


def public_category_text(event: dict[str, Any]) -> str:
    return resolve_public_category(event)["label"]
