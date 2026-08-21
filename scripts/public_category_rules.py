from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT / "shared" / "public-category-taxonomy.json"
TAXONOMY = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
CATEGORIES: dict[str, dict[str, str]] = TAXONOMY["categories"]
ALIASES: dict[str, str] = TAXONOMY["aliases"]
LABEL_ALIASES: dict[str, str] = TAXONOMY["label_aliases"]
GROUPS: dict[str, list[str]] = TAXONOMY["groups"]
RULES = TAXONOMY["rules"]
FALLBACK_ID = TAXONOMY["fallback_category"]
SUMMER_PROGRAM_EVENT_TYPES = set(RULES["summer_program_event_types"])
SUMMER_PROGRAM_RE = re.compile(RULES["summer_program_title_pattern"])
SUMMER_REGISTRATION_RE = re.compile(RULES["summer_registration_title_pattern"])
EXPLICIT_TITLE_RULES = [
    (rule["category"], re.compile(rule["pattern"])) for rule in RULES["explicit_title"]
]
CULTURE_EVIDENCE_RULES = [
    (rule["category"], re.compile(rule["pattern"])) for rule in RULES["culture_evidence"]
]


def fold(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def source_category(event: dict[str, Any]) -> dict[str, str]:
    source = event.get("primary_category") or (event.get("categories") or [None])[0] or {}
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


def evidence_text(event: dict[str, Any]) -> str:
    values = [
        event.get("title"),
        event.get("description"),
        event.get("organizer"),
        event.get("source_name"),
        *(event.get("tags") or []),
    ]
    return fold(" ".join(str(value) for value in values if value))


def is_summer_program(event: dict[str, Any]) -> bool:
    if str(event.get("event_type") or "") not in SUMMER_PROGRAM_EVENT_TYPES:
        return False
    title = fold(event.get("title"))
    return bool(SUMMER_PROGRAM_RE.search(title) or SUMMER_REGISTRATION_RE.search(title))


def category_from_rules(text: str, rules: list[tuple[str, re.Pattern[str]]]) -> dict[str, str] | None:
    for category_id, pattern in rules:
        if pattern.search(text):
            return category(category_id)
    return None


def explicit_title_category(event: dict[str, Any]) -> dict[str, str] | None:
    title = fold(event.get("title"))
    if not title:
        return None
    if SUMMER_PROGRAM_RE.search(title) or is_summer_program(event):
        return category("cursos-talleres-campus")
    return category_from_rules(title, EXPLICIT_TITLE_RULES)


def infer_culture_category(event: dict[str, Any]) -> dict[str, str]:
    explicit = explicit_title_category(event)
    if explicit:
        return explicit
    return category_from_rules(evidence_text(event), CULTURE_EVIDENCE_RULES) or category(FALLBACK_ID)


def resolve_public_category(event: dict[str, Any]) -> dict[str, str]:
    source = source_category(event)
    canonical = canonical_public_category(source)

    if canonical and canonical.get("id") != source.get("id"):
        return dict(canonical)
    if is_summer_program(event):
        return category("cursos-talleres-campus")
    if canonical and canonical.get("id") in CATEGORIES:
        return dict(canonical)
    if source.get("id") == "cultura" or fold(source.get("label")) == "cultura":
        return dict(infer_culture_category(event))
    if not source.get("id") and not source.get("label"):
        return dict(explicit_title_category(event) or category(FALLBACK_ID))

    # Source-specific categories are preserved only when the shared architecture
    # contract registers them. No city renderer may redefine them locally.
    return {"id": source["id"], "label": source.get("label") or source["id"]}


def public_category_text(event: dict[str, Any]) -> str:
    return resolve_public_category(event)["label"]
