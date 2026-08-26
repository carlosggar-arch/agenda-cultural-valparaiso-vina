from __future__ import annotations

import argparse
import copy
import html
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "app"
CITY_REGISTRY = APP_ROOT / "cities.json"
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

# Calendar shells, empty-state copy and navigation labels are never public events.
# These rules are intentionally city-agnostic so every dataset registered in
# app/cities.json receives the same protection.
NON_EVENT_TITLE_PATTERNS = (
    re.compile(r"^0 eventos? encontrados?\b"),
    re.compile(r"^no hay eventos? programados?\b"),
    re.compile(r"^navegacion (?:de )?(?:busqueda y )?vistas? de eventos?\b"),
    re.compile(r"^navegacion de vistas?\b"),
    re.compile(r"^seleccionar fecha\b"),
)

MONTH_NAMES = r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
MONTHLY_PROGRAM_TITLE = re.compile(rf"^(?:agenda\s+|programacion\s+|cartelera\s+)?{MONTH_NAMES}(?:\s+en\s+.+)?$")
PROGRAM_OVERVIEW_TEXT = re.compile(
    r"\b(?:toda nuestra programacion|revisa (?:toda )?la programacion|programacion (?:de|del) mes|"
    r"actividades (?:de|del) mes|programacion en este carrusel)\b"
)
RETROSPECTIVE_OR_NEWS_TEXT = re.compile(
    r"\b(?:hace un ano|celebramos que hace un ano|reabrio sus puertas|"
    r"mas de \d+(?: mil)? personas visitaron|personas visitaron museos|"
    r"balance de visitas|cifras de visitantes|record de visitantes|"
    r"durante estas vacaciones|durante las vacaciones)\b"
)

# Calls for submissions/applications are opportunities, not attendance events.
# A strong call-to-submit signal in the title may carry a parsed deadline in
# schedule.start; therefore this semantic check intentionally runs before the
# generic concrete-schedule early return below.
SUBMISSION_CALL_TITLE = re.compile(
    r"^(?:(?:nueva|abierta)\s+)?convocatoria\b|"
    r"^(?:envia|envianos|manda|comparte|postula|postulate|presenta|inscribe)\s+(?:tu|tus|un|una)\b"
)
SUBMISSION_CALL_LEAD = re.compile(
    r"^(?:(?:nueva|abierta)\s+)?convocatoria\b|"
    r"^(?:abrimos|lanzamos)\s+(?:una\s+)?convocatoria\b"
)
SUBMISSION_DEADLINE_TEXT = re.compile(
    r"\b(?:hasta el|fecha limite|plazo (?:de )?(?:envio|postulacion|recepcion)|"
    r"cierre (?:de la |de )?(?:convocatoria|postulaciones|recepcion)|"
    r"postulaciones? (?:abiertas? )?hasta|recepcion (?:de \w+ ){0,3}hasta)\b"
)


# Administrative application support is useful information, but it is not an
# attendance event. Keep this deliberately narrower than the generic
# submission-call rule: require an applicant-directed administrative action
# plus an explicit support resource, and never suppress a scheduled activity.
ADMIN_APPLICATION_ACTION = re.compile(
    r"\b(?:quieres|vas a|necesitas|puedes|debes)\s+(?:postular|solicitar)\b|"
    r"\b(?:solicita|solicitar|solicitudes?|postula|postulate)\b|"
    r"\b(?:se encuentra|esta)\s+abierta\s+la\s+convocatoria\b"
)
ADMIN_APPLICATION_SUPPORT = re.compile(
    r"\bcartas?\s+de\s+apoyo\b|"
    r"\brespaldo\s+(?:municipal|institucional)\b|"
    r"\bapoyo\s+(?:municipal|institucional)\s+(?:para|a)\s+(?:(?:tu|su|la)\s+)?postulacion\b"
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
DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")


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
    # Remove scraper escape artifacts: literal backslash-n/backslash-r or backslash + real newline.
    text = re.sub(r"\\(?:n|r|\r?\n)", " ", text)
    text = text.replace("\\", " ")
    text = clean_space(text)
    # Repair the one-character legacy artifact produced by the previous sanitizer version.
    text = re.sub(r"(?<=[.!?])\s+n\s*$", "", text)
    return text


def is_generic_title(value: object) -> bool:
    title = clean_space(value)
    return bool(title and any(pattern.search(title) for pattern in GENERIC_TITLE_PATTERNS))


def is_non_event_title(value: object) -> bool:
    title = fold(clean_html_text(value))
    return bool(title and any(pattern.search(title) for pattern in NON_EVENT_TITLE_PATTERNS))


def has_concrete_schedule(event: dict) -> bool:
    schedule = event.get("schedule") or {}
    if clean_space(schedule.get("start")) or clean_space(schedule.get("end")):
        return True
    occurrences = schedule.get("occurrences")
    if isinstance(occurrences, list):
        return any(clean_space((item or {}).get("start") or (item or {}).get("end")) for item in occurrences)
    return False


def is_deadline_only_submission_call(event: dict) -> bool:
    title = fold(event.get("title"))
    description = fold(event.get("description"))
    combined = f"{title} {description}".strip()
    if not SUBMISSION_DEADLINE_TEXT.search(combined):
        return False
    # Title-level intent is authoritative even when a scraper promoted the
    # deadline itself into schedule.start. Description-only intent is accepted
    # only when there is no independent attendance schedule, which protects
    # real workshops/performances that merely have an application deadline.
    if SUBMISSION_CALL_TITLE.search(title):
        return True
    description_lead = description[:240]
    return bool(SUBMISSION_CALL_LEAD.search(description_lead) and not has_concrete_schedule(event))



def is_administrative_application_support(event: dict) -> bool:
    if has_concrete_schedule(event):
        return False
    title = fold(event.get("title"))
    description = fold(event.get("description"))
    combined = f"{title} {description}".strip()
    return bool(
        ADMIN_APPLICATION_ACTION.search(combined)
        and ADMIN_APPLICATION_SUPPORT.search(combined)
    )

def non_event_context_reason(event: dict) -> str | None:
    if str(event.get("event_type") or "event") != "event":
        return None
    if is_deadline_only_submission_call(event):
        return "call_for_submissions_deadline_not_event"
    if is_administrative_application_support(event):
        return "administrative_application_support_not_event"
    if has_concrete_schedule(event):
        return None
    title = fold(event.get("title"))
    description = fold(event.get("description"))
    combined = f"{title} {description}".strip()
    if MONTHLY_PROGRAM_TITLE.search(title) and PROGRAM_OVERVIEW_TEXT.search(combined):
        return "monthly_program_overview_without_event_schedule"
    if RETROSPECTIVE_OR_NEWS_TEXT.search(combined):
        return "institutional_news_or_retrospective_without_event_schedule"
    return None


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
    # Human venue name is the stable cross-source identity; venue_id is only a fallback.
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


def parse_schedule_date(value: object) -> date | None:
    match = DATE_PREFIX.match(clean_space(value))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def reference_date(dataset: dict) -> date | None:
    value = clean_space(dataset.get("publication_date"))
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def prune_expired_schedule(event: dict, reference: date) -> tuple[bool, int]:
    """Return (keep_event, pruned_occurrence_count) using the dataset publication date."""
    schedule = copy.deepcopy(event.get("schedule") or {})
    occurrences = schedule.get("occurrences")
    pruned = 0

    if isinstance(occurrences, list) and occurrences:
        kept_occurrences = []
        for occurrence in occurrences:
            occurrence = occurrence or {}
            occurrence_end = parse_schedule_date(occurrence.get("end") or occurrence.get("start"))
            if occurrence_end is not None and occurrence_end < reference:
                pruned += 1
                continue
            kept_occurrences.append(occurrence)
        schedule["occurrences"] = kept_occurrences
        event["schedule"] = schedule
        if not kept_occurrences:
            return False, pruned
        return True, pruned

    end_date = parse_schedule_date(schedule.get("end"))
    start_date = parse_schedule_date(schedule.get("start"))
    effective_end = end_date or start_date
    if effective_end is not None and effective_end < reference:
        return False, pruned
    return True, pruned


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
        "expired_removed": [],
        "past_occurrences_pruned": [],
    }
    publication_day = reference_date(dataset)

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

        if is_non_event_title(event.get("title")):
            changes["quarantined"].append({
                "id": event_id,
                "title": event.get("title"),
                "reason": "calendar_navigation_or_empty_state",
            })
            continue

        context_reason = non_event_context_reason(event)
        if context_reason:
            changes["quarantined"].append({
                "id": event_id,
                "title": event.get("title"),
                "reason": context_reason,
            })
            continue

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

        if publication_day is not None:
            keep, pruned = prune_expired_schedule(event, publication_day)
            if pruned:
                changes["past_occurrences_pruned"].append({"id": event_id, "count": pruned})
            if not keep:
                changes["expired_removed"].append({
                    "id": event_id,
                    "title": event.get("title"),
                    "reason": "schedule_ended_before_publication_date",
                })
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


def resolve_registry_dataset(value: object) -> Path:
    raw = clean_space(value)
    if not raw:
        raise ValueError("City registry contains an empty dataset path")
    candidate = (APP_ROOT / raw).resolve()
    root = ROOT.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Dataset path escapes repository root: {raw}")
    return candidate


def configured_datasets(registry_path: Path = CITY_REGISTRY) -> list[tuple[str, Path]]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    result: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for city in registry.get("cities") or []:
        city_id = clean_space(city.get("id"))
        dataset_path = resolve_registry_dataset(city.get("dataset"))
        if not city_id or dataset_path in seen:
            continue
        seen.add(dataset_path)
        result.append((city_id, dataset_path))
    if not result:
        raise ValueError("City registry does not define public datasets")
    return result


def sanitize_dataset(dataset_path: Path) -> tuple[dict, dict]:
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
    return dataset, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitize public content, dates, titles and duplicate exhibitions.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--all-cities", action="store_true", help="Apply the same guard to every dataset registered in app/cities.json.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report_path = Path(args.report)
    targets = configured_datasets() if args.all_cities else [("dataset", Path(args.dataset))]
    city_reports: list[dict] = []
    sanitized_payloads: list[tuple[Path, dict]] = []

    for city_id, dataset_path in targets:
        dataset, report = sanitize_dataset(dataset_path)
        report["city_id"] = city_id
        city_reports.append(report)
        sanitized_payloads.append((dataset_path, dataset))

    if args.all_cities:
        report = {
            "status": "ok",
            "mode": "all_cities",
            "registry": str(CITY_REGISTRY),
            "datasets": city_reports,
            "events_before": sum(item["events_before"] for item in city_reports),
            "events_after": sum(item["events_after"] for item in city_reports),
            "removed": sum(item["removed"] for item in city_reports),
        }
    else:
        report = city_reports[0]

    if not args.no_write:
        for dataset_path, dataset in sanitized_payloads:
            dataset_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
