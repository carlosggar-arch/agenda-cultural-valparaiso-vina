from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.public_category_rules import classify_public_category
from refresh_portaltickets_editorial import PortalTokenParser, SOURCE_ID, fetch_url, norm

DATASET = ROOT / "agenda_web.json"

SECTION_HEADINGS = {
    "fecha",
    "lugar",
    "produce",
    "descripcion",
    "tickets disponibles",
    "todos los eventos",
    "ver mapa",
    "grupo region",
    "artistas y tags relacionados",
    "politicas de reembolso",
    "contacto",
    "links relacionados",
}
MUSIC_PRODUCER_RE = re.compile(
    r"\b(?:records?|recordings?|music|musica|sello discografico|discografica)\b",
    re.I,
)


def _clean_section_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
    cleaned = re.sub(r"\s*\(\+\)\s*$", "", cleaned).strip()
    return cleaned


def _section_values(texts: list[str], heading: str) -> list[str]:
    wanted = norm(heading)
    start = next((index for index, text in enumerate(texts) if norm(text) == wanted), None)
    if start is None:
        return []
    values: list[str] = []
    for raw in texts[start + 1 :]:
        cleaned = _clean_section_value(raw)
        normalized = norm(cleaned)
        if not cleaned:
            continue
        if normalized in SECTION_HEADINGS:
            break
        values.append(cleaned)
    return values


def parse_structured_metadata(markup: str) -> dict[str, Any]:
    parser = PortalTokenParser()
    parser.feed(markup)
    parser.close()
    texts = [
        str(token.get("text") or "").strip()
        for token in parser.tokens
        if str(token.get("text") or "").strip()
    ]
    related = _section_values(texts, "artistas y tags relacionados")
    producers = _section_values(texts, "produce")
    producer = producers[0] if producers else None
    return {
        "related_entities": related[:24],
        "producer": producer,
    }


def _music_producer_hint(producer: object) -> bool:
    return bool(MUSIC_PRODUCER_RE.search(norm(producer)))


def _compose_semantic_text(event: dict[str, Any], metadata: dict[str, Any]) -> str:
    semantics = event.get("semantics") if isinstance(event.get("semantics"), dict) else {}
    parts: list[str] = []
    existing = str(semantics.get("category_evidence_text") or event.get("description") or "").strip()
    if existing:
        parts.append(existing)
    for value in metadata.get("related_entities") or []:
        cleaned = _clean_section_value(str(value or ""))
        if cleaned:
            parts.append(cleaned)
    producer = _clean_section_value(str(metadata.get("producer") or ""))
    if producer:
        parts.append(producer)
    # PortalTickets exposes the producer as structured source metadata. A producer
    # explicitly named as a record/music label is strong format evidence, unlike
    # a generic venue or organizer string. Convert only that strong structural
    # signal into the shared taxonomy vocabulary; opaque producer names remain
    # neutral and therefore cannot force a category.
    if _music_producer_hint(producer):
        parts.append("música")

    result: list[str] = []
    seen: set[str] = set()
    for value in parts:
        key = norm(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return " ".join(result)[:2000].strip()


def enrich_from_structured_metadata(event: dict[str, Any], metadata: dict[str, Any]) -> bool:
    semantics = event.setdefault("semantics", {})
    structured: dict[str, Any] = {}
    related = [
        _clean_section_value(str(value or ""))
        for value in metadata.get("related_entities") or []
        if _clean_section_value(str(value or ""))
    ]
    producer = _clean_section_value(str(metadata.get("producer") or ""))
    if related:
        structured["related_entities"] = related
    if producer:
        structured["producer"] = producer
    if structured:
        semantics["source_structured_evidence"] = structured

    semantic_text = _compose_semantic_text(event, metadata)
    if semantic_text:
        semantics["category_evidence_text"] = semantic_text

    probe = dict(event)
    probe["description"] = semantic_text or None
    classification = classify_public_category(probe)
    category = dict(classification["category"])
    editorial = event.setdefault("editorial", {})
    editorial["structured_semantic_enrichment"] = bool(structured)
    editorial["category_classifier"] = "shared_public_category"
    editorial["category_confidence"] = classification.get("confidence")
    if category.get("id") == "unclassified":
        return False

    event["primary_category"] = category
    event["categories"] = [category]
    return True


def _reference_day(payload: dict[str, Any]) -> str:
    return str(payload.get("generated_at") or payload.get("publication_date") or "")[:10]


def _is_current_or_future(item: dict[str, Any], reference_day: str) -> bool:
    start_day = str((item.get("schedule") or {}).get("start") or "")[:10]
    return not reference_day or not start_day or start_day >= reference_day


def _is_unclassified(item: dict[str, Any]) -> bool:
    return classify_public_category(item)["category"]["id"] == "unclassified"


def _pending(payload: dict[str, Any]) -> list[dict[str, Any]]:
    reference_day = _reference_day(payload)
    return [
        item
        for item in payload.get("events") or []
        if str(item.get("source_id") or "") == SOURCE_ID
        and _is_current_or_future(item, reference_day)
        and _is_unclassified(item)
    ]


def _self_test() -> None:
    markup = """
    <h4>ARTISTAS Y TAGS RELACIONADOS</h4>
    <div>FUE CULPA DE MACKENZIE</div><div>INMA</div>
    <h4>Produce:</h4><div>Wareba Records (+)</div>
    <div>Ver Mapa</div><h4>Descripción</h4><p>Texto neutro sin categoría.</p>
    """
    metadata = parse_structured_metadata(markup)
    assert metadata == {
        "related_entities": ["FUE CULPA DE MACKENZIE", "INMA"],
        "producer": "Wareba Records",
    }, metadata
    opaque = {
        "id": "fixture",
        "title": "Nombre opaco",
        "event_type": "event",
        "primary_category": {"id": "otros", "label": "Otros panoramas"},
        "categories": [{"id": "otros", "label": "Otros panoramas"}],
        "description": "Texto neutro sin categoría.",
        "tags": ["PortalTickets"],
        "source_id": SOURCE_ID,
        "semantics": {"source_category": {"id": "cultura", "label": "Cultura"}},
    }
    assert enrich_from_structured_metadata(opaque, metadata) is True
    assert opaque["primary_category"]["id"] == "musica", opaque

    ambiguous = {
        "id": "fixture-ambiguous",
        "title": "Nombre opaco",
        "event_type": "event",
        "primary_category": {"id": "otros", "label": "Otros panoramas"},
        "categories": [{"id": "otros", "label": "Otros panoramas"}],
        "description": "Texto neutro sin categoría.",
        "tags": ["PortalTickets"],
        "source_id": SOURCE_ID,
        "semantics": {"source_category": {"id": "cultura", "label": "Cultura"}},
    }
    assert enrich_from_structured_metadata(
        ambiguous,
        {"related_entities": ["PROYECTO X"], "producer": "Independiente"},
    ) is False
    assert classify_public_category(ambiguous)["category"]["id"] == "unclassified"


def main() -> int:
    _self_test()
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    pending = _pending(payload)
    stats = {
        "pending_before": len(pending),
        "fetched": 0,
        "fetch_failed": 0,
        "structured_found": 0,
        "resolved": 0,
    }

    for event in pending:
        url = str((event.get("links") or {}).get("tickets") or (event.get("links") or {}).get("source") or "").strip()
        if not url:
            stats["fetch_failed"] += 1
            continue
        ok, _status, markup, _error = fetch_url(url)
        if not ok or not markup:
            stats["fetch_failed"] += 1
            continue
        stats["fetched"] += 1
        metadata = parse_structured_metadata(markup)
        if metadata.get("related_entities") or metadata.get("producer"):
            stats["structured_found"] += 1
        if enrich_from_structured_metadata(event, metadata):
            stats["resolved"] += 1

    remaining = _pending(payload)
    if stats["resolved"] or stats["structured_found"]:
        DATASET.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        **stats,
        "pending_after": len(remaining),
        "remaining": [
            {"id": item.get("id"), "title": item.get("title")}
            for item in remaining
        ],
    }
    print("PORTALTICKETS_STRUCTURED_SEMANTICS=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    if remaining:
        raise SystemExit(
            "PORTALTICKETS_STRUCTURED_SEMANTICS_UNRESOLVED ids="
            + ",".join(str(item.get("id") or "") for item in remaining)
        )
    print("PORTALTICKETS_STRUCTURED_SEMANTICS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
