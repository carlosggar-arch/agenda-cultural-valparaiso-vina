from __future__ import annotations

import argparse
import copy
import html
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "agenda_web.json"
DEFAULT_REPORT = ROOT / "app/data/quality/content-quality.json"

SOCIAL_HOSTS = {"instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com", "tiktok.com", "www.tiktok.com"}
GENERIC_TITLE_PATTERNS = (
    re.compile(r"^(?:les|los|te) esperamos(?:\b|$)", re.I),
    re.compile(r"^(?:les|los|te) invitamos(?:\b|$)", re.I),
    re.compile(r"^estamos de celebraci[oó]n(?:\b|$)", re.I),
    re.compile(r"^no (?:te|se) lo pierd(?:as|an)(?:\b|$)", re.I),
    re.compile(r"^ven a (?:disfrutar|conocer|visitarnos)(?:\b|$)", re.I),
)

ACTIVITY_NOUN = r"(?:muestra|exposici[oó]n|exhibici[oó]n|concierto|recital|obra|taller|charla|conversatorio|festival|funci[oó]n|encuentro|seminario|curso)"
RECOVERY_PATTERNS = (
    re.compile(
        rf"(?:ceremonia\s+de\s+)?(?:inauguraci[oó]n|apertura|presentaci[oó]n)\s+de\s+(?:la|el)?\s*({ACTIVITY_NOUN}[^,.;\n]{{3,130}})",
        re.I,
    ),
    re.compile(rf"(?:en|para)\s+un(?:a)?\s+({ACTIVITY_NOUN}[^,.;\n]{{3,130}})", re.I),
    re.compile(rf"\b({ACTIVITY_NOUN}\s+(?:titulad[ao]\s+|llamad[ao]\s+)?[“\"«][^”\"»]{{3,120}}[”\"»])", re.I),
)

CANONICAL_PREFIX = re.compile(
    r"^(?:(?:exposici[oó]n|exhibici[oó]n|muestra)\s+(?:temporal|transitoria)|(?:exposici[oó]n|exhibici[oó]n|muestra))\s*(?://|:|[-–—])\s*",
    re.I,
)
OUTER_QUOTES = re.compile(r"^[\s'\"“”«»]+|[\s'\"“”«»]+$")
HTML_TAG = re.compile(r"<[^>]+>")
SPACE = re.compile(r"\s+")


def clean_space(value: object) -> str:
    return SPACE.sub(" ", str(value or "")).strip()


def fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean_space(value))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_html_text(value: object) -> str:
    raw = str(value or "")
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"<\s*(?:br|/p|/div|/li|/h[1-6])\s*/?>", " ", text, flags=re.I)
    text = HTML_TAG.sub(" ", text)
    # Scrapers occasionally leave a literal \\n/\\r token or a backslash directly
    # before a real newline. Remove the complete escape, not only the slash.
    text = re.sub(r"\\(?:n|r|\r?\n)", " ", text)
    text = text.replace("\\", " ")
    text = clean_space(text)
    # Repair the legacy artifact produced by the previous sanitizer version.
    text = re.sub(r"(?<=[.!?])\s+n\s*$", "", text)
    return text


def is_generic_title(value: object) -> bool:
    title = clean_space(value)
    return bool(title and any(pattern.search(title) for pattern in GENERIC_TITLE_PATTERNS))


def _clean_recovered_title(value: str) -> str:
    title = clean_html_text(value)
    title = title.rstrip(" .,:;–—-").strip()
    return OUTER_QUOTES.sub("", title).strip()


def recover_generic_title(event: dict) -> tuple[str | None, str | None]:
    if not is_generic_title(event.get("title")):
        return None, None
    description = clean_html_text(event.get("description"))
    if not description:
        return None, None

    for pattern in RECOVERY_PATTERNS:
        match = pattern.search(description)
        if not match:
            continue
        candidate = _clean_recovered_title(match.group(1))
        words = fold(candidate).split()
        if 2 <= len(words) <= 18 and fold(candidate) != fold(event.get("location", {}).get("venue")):
            return candidate, "explicit_activity_phrase_in_description"
    return None, None


def canonical_exhibition_title(value: object) -> str:
    title = clean_html_text(value)
    title = CANONICAL_PREFIX.sub("", title)
    title = OUTER_QUOTES.sub("", title).rstrip(" .,:;–—-").strip()
    return fold(title)


def venue_key(event: dict) -> str:
    location = event.get("location") or {}
    venue = fold(location.get("venue"))
    city = fold(location.get("city"))
    # Use the human venue name as the stable cross-source identity. One source may
    # provide venue_id while another source for the same place does not.
    if venue:
        if city and venue.endswith(f" {city}"):
            venue = venue[: -(len(city) + 1)].strip()
        return f"{venue}|{city}"
    venue_id = fold(location.get("venue_id"))
    return f"id:{venue_id}" if venue_id else ""


def is_exhibition(event: dict) -> bool:
    category = event.get("primary_category") or {}
    category_id = fold(category.get("id"))
    label = fold(category.get("label"))
    return category_id in {"exposiciones", "museos"} or label in {"exposiciones", "museos"}


def source_url(event: dict) -> str:
    links = event.get("links") or {}
    return clean_space(event.get("source_url") or links.get("official") or links.get("source"))


def is_social_url(value: str) -> bool:
    try:
        host = urlparse(value).hostname or ""
    except Exception:
        return False
    return host.casefold() in SOCIAL_HOSTS


def event_score(event: dict) -> tuple[int, int, int]:
    status = event.get("public_status") or {}
    url = source_url(event)
    score = 0
    if url and not is_social_url(url):
        score += 50
    if status.get("source_official") is True:
        score += 20
    if status.get("information_completeness") == "complete":
        score += 10
    if clean_space((event.get("schedule") or {}).get("end")):
        score += 4
    if clean_space((event.get("image") or {}).get("url")):
        score += 2
    if clean_space((event.get("links") or {}).get("official")):
        score += 2
    description_len = len(clean_space(event.get("description")))
    return score, min(description_len, 1000), -len(clean_space(event.get("title")))


def merge_missing(preferred: dict, duplicate: dict) -> None:
    for field in ("image", "price"):
        current = preferred.get(field) or {}
        other = duplicate.get(field) or {}
        if not isinstance(current, dict) or not isinstance(other, dict):
            continue
        merged = copy.deepcopy(current)
        for key, value in other.items():
            if merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                merged[key] = copy.deepcopy(value)
        preferred[field] = merged

    schedule = copy.deepcopy(preferred.get("schedule") or {})
    other_schedule = duplicate.get("schedule") or {}
    for key in ("opening_hours", "opening_time", "closing_time", "hours_confidence"):
        if schedule.get(key) in (None, "", [], {}) and other_schedule.get(key) not in (None, "", [], {}):
            schedule[key] = copy.deepcopy(other_schedule[key])
    preferred["schedule"] = schedule

    editorial = copy.deepcopy(preferred.get("editorial") or {})
    sources = editorial.get("duplicate_sources") or []
    duplicate_source = {
        "id": duplicate.get("id"),
        "title": duplicate.get("title"),
        "source_name": duplicate.get("source_name"),
        "source_url": source_url(duplicate),
    }
    if duplicate_source not in sources:
        sources.append(duplicate_source)
    editorial["duplicate_sources"] = sources
    editorial["duplicates_consolidated"] = len(sources)
    preferred["editorial"] = editorial


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    counts = dict(dataset.get("counts") or {})
    counts["total"] = len(events)
    counts["events"] = sum(1 for event in events if event.get("event_type") == "event")
    counts["courses"] = sum(1 for event in events if event.get("event_type") == "course")
    counts["flexible_offers"] = sum(1 for event in events if event.get("event_type") == "flexible_offer")
    counts["programs"] = sum(1 for event in events if event.get("event_type") == "program")
    dataset["counts"] = counts


def apply_guard(dataset: dict) -> dict:
    events = list(dataset.get("events") or [])
    changes: dict[str, list] = {
        "html_cleaned": [],
        "titles_recovered": [],
        "duplicates_consolidated": [],
        "quarantined": [],
    }

    sanitized: list[dict] = []
    for event in events:
        event = copy.deepcopy(event)
        event_id = str(event.get("id") or "")

        old_description = str(event.get("description") or "")
        new_description = clean_html_text(old_description)
        if old_description and new_description != clean_space(old_description):
            event["description"] = new_description
            changes["html_cleaned"].append(event_id)

        old_title = clean_html_text(event.get("title"))
        if old_title and old_title != event.get("title"):
            event["title"] = old_title

        recovered, reason = recover_generic_title(event)
        if recovered and reason:
            original = clean_space(event.get("title"))
            event["title"] = recovered
            image = copy.deepcopy(event.get("image") or {})
            if fold(image.get("alt")) == fold(original):
                image["alt"] = recovered
                event["image"] = image
            editorial = copy.deepcopy(event.get("editorial") or {})
            editorial.setdefault("title_original", original)
            editorial["title_recovered"] = True
            editorial["title_recovery_reason"] = reason
            event["editorial"] = editorial
            changes["titles_recovered"].append({"id": event_id, "from": original, "to": recovered, "reason": reason})
        elif is_generic_title(event.get("title")):
            changes["quarantined"].append({"id": event_id, "title": event.get("title"), "reason": "generic_title_without_explicit_recovery"})
            continue

        sanitized.append(event)

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event in sanitized:
        if not is_exhibition(event):
            continue
        canonical = canonical_exhibition_title(event.get("title"))
        key = venue_key(event)
        if canonical and key:
            groups[(key, canonical)].append(event)

    removed_ids: set[str] = set()
    for (key, canonical), members in groups.items():
        if len(members) < 2:
            continue
        preferred = max(members, key=event_score)
        canonical_title = CANONICAL_PREFIX.sub("", clean_html_text(preferred.get("title"))).strip().rstrip(" .,:;–—-")
        canonical_title = OUTER_QUOTES.sub("", canonical_title).strip()
        if canonical_title:
            preferred["title"] = canonical_title
        duplicates = [event for event in members if event is not preferred]
        for duplicate in duplicates:
            merge_missing(preferred, duplicate)
            removed_ids.add(str(duplicate.get("id") or ""))
        changes["duplicates_consolidated"].append({
            "venue_key": key,
            "canonical_title": canonical,
            "kept_id": preferred.get("id"),
            "removed_ids": [event.get("id") for event in duplicates],
        })

    dataset["events"] = [event for event in sanitized if str(event.get("id") or "") not in removed_ids]
    refresh_counts(dataset)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitize public content, recover generic titles, and consolidate duplicate exhibitions.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    report_path = Path(args.report)
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    before = len(dataset.get("events") or [])
    changes = apply_guard(dataset)
    after = len(dataset.get("events") or [])

    report = {
        "status": "ok",
        "dataset": str(dataset_path),
        "events_before": before,
        "events_after": after,
        "removed": before - after,
        **changes,
    }

    if not args.no_write:
        dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
