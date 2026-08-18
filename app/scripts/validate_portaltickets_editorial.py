from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "agenda_web.json"
SOURCE_ID = "portaltickets_valparaiso"
SOURCE_URL = "https://www.portaldisc.com/tickets/R05"
OUT_OF_SCOPE = {"san antonio", "casablanca", "limache", "quilpue", "villa alemana", "quintero", "puchuncavi", "concon", "el quisco", "el tabo", "algarrobo", "cartagena", "la ligua", "zapallar", "papudo", "olmue", "los andes", "san felipe"}
ADDRESS_HINT = re.compile(r"\b(?:av\.?|avenida|calle|viana|agua santa|brasil|alemania|antofagasta|eusebio lillo|gral\.?|general|carcel|cárcel|ortiz de rozas|socrates|sócrates)\b", re.I)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def validate_event(item: dict) -> list[str]:
    errors: list[str] = []
    if str(item.get("source_id") or "") != SOURCE_ID:
        return errors
    title = str(item.get("title") or "")
    location = item.get("location") or {}
    venue = str(location.get("venue") or "")
    city = norm(location.get("city"))
    haystack = norm(f"{title} {venue} {location.get('address') or ''}")
    if city not in {"valparaiso", "vina del mar"}: errors.append("invalid_city")
    if any(marker in haystack for marker in OUT_OF_SCOPE): errors.append("out_of_scope")
    if norm(title) == norm(venue): errors.append("title_equals_venue")
    if ADDRESS_HINT.search(title) and re.search(r"\b\d{2,5}\b", title): errors.append("address_used_as_title")
    if item.get("organizer") is not None: errors.append("organizer_should_be_unknown")
    if (item.get("public_status") or {}).get("source_official") is not False: errors.append("secondary_source_marked_official")
    if str((item.get("editorial") or {}).get("reason") or "") != "secondary_ticketing_source:portaltickets_valparaiso": errors.append("legacy_editorial_reason")
    links = item.get("links") or {}
    ticket = str(links.get("tickets") or "")
    if not ticket or ticket.rstrip("/") == SOURCE_URL.rstrip("/"):
        errors.append("missing_individual_ticket")
    elif urlparse(ticket).scheme not in {"http", "https"}:
        errors.append("invalid_ticket_url")
    if links.get("official") is not None: errors.append("ticketing_source_used_as_official")
    return errors


def validate_dataset(dataset: dict) -> dict:
    portal = [item for item in dataset.get("events") or [] if str(item.get("source_id") or "") == SOURCE_ID]
    failures = [{"id": item.get("id"), "title": item.get("title"), "errors": validate_event(item)} for item in portal if validate_event(item)]
    ids = [str(item.get("id") or "") for item in portal]
    if len(ids) != len(set(ids)): failures.append({"id": None, "title": None, "errors": ["duplicate_portaltickets_ids"]})
    return {"portal_events": len(portal), "failures": failures}


def main() -> None:
    report = validate_dataset(json.loads(DATASET.read_text(encoding="utf-8")))
    if report["failures"]:
        raise SystemExit("PORTALTICKETS_EDITORIAL_INVALID " + json.dumps(report, ensure_ascii=False))
    print("PORTALTICKETS_EDITORIAL_OK " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
