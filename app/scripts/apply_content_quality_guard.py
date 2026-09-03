from __future__ import annotations

import argparse
import copy
import html
import json
import os
import re
import subprocess
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from app.scripts.transformation_receipt_ledger import (
        append_receipt, empty_ledger, load_ledger, make_receipt, occurrence_id, semantic_payload,
    )
except ModuleNotFoundError:  # Direct script execution used by repository contracts.
    from transformation_receipt_ledger import (
        append_receipt, empty_ledger, load_ledger, make_receipt, occurrence_id, semantic_payload,
    )

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "app"
CITY_REGISTRY = APP_ROOT / "cities.json"
DEFAULT_DATASET = ROOT / "agenda_web.json"
DEFAULT_REPORT = ROOT / "app/data/quality/content-quality.json"
DEFAULT_LEDGER = ROOT / "app/data/quality/transformation-receipts.json"

SOCIAL_HOSTS = {"instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com", "tiktok.com", "www.tiktok.com"}
GENERIC_TITLE_PATTERNS = (
    re.compile(r"^(?:les|los|te) esperamos(?:\b|$)", re.I),
    re.compile(r"^(?:les|los|te) invitamos(?:\b|$)", re.I),
    re.compile(r"^estamos de celebraci[oó]n(?:\b|$)", re.I),
    re.compile(r"^no (?:te|se) lo pierd(?:as|an)(?:\b|$)", re.I),
    re.compile(r"^ven a (?:disfrutar|conocer|visitarnos)(?:\b|$)", re.I),
    re.compile(r"^las? bases?\b.*\bhistoria\b", re.I),
    re.compile(r"^(?:link|enlace) en (?:la )?bio(?:grafia)?\b", re.I),
    re.compile(r"^pronto(?:\b|[.…!])", re.I),
    re.compile(r"^se llena\b.*\breserv", re.I),
    re.compile(r"^#[\w.-]+$", re.I),
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
    r"postulaciones? (?:abiertas? )?hasta|recepcion (?:de \w+ ){0,3}hasta|"
    r"cierre de (?:la )?(?:edicion|concurso|certamen).{0,80}\b(?:poeta|poesia|relato|obra))\b"
)
SUBMISSION_CONTEST_TEXT = re.compile(
    r"\b(?:bases?|convocatoria|se busca)\b.{0,80}\b(?:poeta|poesia|relato|obra|postulacion)\b|"
    r"\b(?:poeta|poesia|relato|obra)\b.{0,80}\b(?:bases?|convocatoria|se busca)\b"
)
GIVEAWAY_ACTION = re.compile(r"\b(?:sorteo|particip(?:a|ar|ando)|etiquet(?:a|as)|compart(?:e|es)|seguir la cuenta)\b")
GIVEAWAY_PRIZE = re.compile(r"\b(?:ganador|ganadora|premio|regalarte|estad[ií]a|escapada para dos)\b")
MULTI_EVENT_DECLARATION = re.compile(r"\b(?:dos|tres|varios|varias)\s+(?:encuentros?|eventos?|actividades?|funciones?)\b")
MULTI_EVENT_SEGMENTS = re.compile(r"\b(?:primer(?:o|a|ito|ita)|segund(?:o|a|ito|ita))\b")
ADDRESS_PARENTHETICAL = re.compile(r"\([^)]*\b\d{1,5}\b[^)]*\)")


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
OFFICIAL_EXPIRED_TEXT = re.compile(r"\bfinaliz(?:ad[oa]s?|do|o)\b", re.I)


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
    if SUBMISSION_CONTEST_TEXT.search(combined) and re.search(r"\b(?:cierre|bases?|convocatoria)\b", combined):
        return True
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


def materialize_submission_call(event: dict) -> bool:
    """Turn a verified cultural call into a non-attendance public opportunity."""
    if not is_deadline_only_submission_call(event):
        return False
    status = event.get("public_status") if isinstance(event.get("public_status"), dict) else {}
    if status.get("source_official") is not True or not source_url(event):
        return False
    description = clean_html_text(event.get("description"))
    title_match = re.search(
        r"(?:edici.n|convocatoria|concurso)\s+(?:de\s+)?[“\"]?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 ]{3,80})[”\"]?",
        description,
    )
    if title_match and is_generic_title(event.get("title")):
        event["title"] = _clean_recovered_title(title_match.group(1))
    schedule = event.get("schedule") if isinstance(event.get("schedule"), dict) else {}
    deadline = clean_space(schedule.get("end") or schedule.get("start"))
    deadline_day = deadline[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", deadline) else None
    event["content_kind"] = "call_for_submissions"
    event["event_type"] = "call_for_submissions"
    event["schedule"] = {
        "mode": "deadline", "start": None, "end": deadline_day, "occurrences": [],
        "display_text": f"Postulaciones hasta el {deadline_day}" if deadline_day else "Consulta las bases",
    }
    event["submission"] = {"deadline": deadline_day, "attendance_occurrence": False}
    links = copy.deepcopy(event.get("links") or {})
    links["participation"] = links.get("registration") or links.get("official") or links.get("source") or source_url(event)
    event["links"] = links
    editorial = copy.deepcopy(event.get("editorial") or {})
    editorial["content_kind_authority"] = "verified_official_submission_call"
    event["editorial"] = editorial
    return True


def submission_call_missing_evidence(event: dict) -> list[str]:
    """Explain why a detected call cannot become a public opportunity yet."""
    if not is_deadline_only_submission_call(event):
        return []
    status = event.get("public_status") if isinstance(event.get("public_status"), dict) else {}
    links = event.get("links") if isinstance(event.get("links"), dict) else {}
    provenance = event.get("provenance") if isinstance(event.get("provenance"), dict) else {}
    missing: list[str] = []
    if status.get("source_official") is not True:
        missing.append("verified_official_source")
    if not source_url(event):
        missing.append("source_url")
    if not (links.get("registration") or links.get("participation") or links.get("official")):
        missing.append("official_bases_or_participation_url")
    if not provenance:
        missing.append("field_provenance")
    return missing


def is_promotional_giveaway(event: dict) -> bool:
    combined = f"{fold(event.get('title'))} {fold(event.get('description'))}".strip()
    return bool(GIVEAWAY_ACTION.search(combined) and GIVEAWAY_PRIZE.search(combined))


def is_contaminated_multi_event_record(event: dict) -> bool:
    """Detect inseparable composites; require all signals to avoid truncation false positives."""
    title = clean_space(event.get("title"))
    description_raw = clean_space(event.get("description"))
    description = fold(description_raw)
    location = event.get("location") if isinstance(event.get("location"), dict) else {}
    expected_place = fold(location.get("city") or location.get("commune"))
    title_place = fold(title)
    has_foreign_address_segment = bool(ADDRESS_PARENTHETICAL.search(title) and expected_place and expected_place not in title_place)
    is_truncated = description_raw.endswith("...") or description_raw.endswith("…")
    return bool(
        MULTI_EVENT_DECLARATION.search(description)
        and len(MULTI_EVENT_SEGMENTS.findall(description)) >= 2
        and has_foreign_address_segment
        and is_truncated
    )



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
        return "unverified_call_for_submissions_missing_official_bases"
    if is_promotional_giveaway(event):
        return "promotional_giveaway_not_attendance_event"
    if is_contaminated_multi_event_record(event):
        return "multi_event_geography_conflict_with_truncated_segment"
    if is_administrative_application_support(event):
        return "administrative_application_support_not_event"
    title = fold(event.get("title"))
    description = fold(event.get("description"))
    if clean_space(event.get("title")).startswith("#") and not has_concrete_schedule(event):
        if re.search(r"\b(?:programacion|cartelera)\b", description):
            return "promotional_carousel_without_verified_children"
    if has_concrete_schedule(event):
        return None
    combined = f"{title} {description}".strip()
    if MONTHLY_PROGRAM_TITLE.search(title) and PROGRAM_OVERVIEW_TEXT.search(combined):
        return "monthly_program_overview_without_event_schedule"
    if RETROSPECTIVE_OR_NEWS_TEXT.search(combined):
        return "institutional_news_or_retrospective_without_event_schedule"
    return None


def explicit_publication_review_reason(event: dict) -> tuple[str, list[str]] | None:
    """Honor an upstream evidence review without encoding editorial cases here."""
    editorial = event.get("editorial") if isinstance(event.get("editorial"), dict) else {}
    if editorial.get("publication_review_required") is not True:
        return None
    reason = clean_space(editorial.get("publication_review_reason"))
    missing = editorial.get("publication_review_missing_evidence")
    if not reason or not isinstance(missing, list) or not all(clean_space(item) for item in missing):
        return None
    return reason, [clean_space(item) for item in missing]


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


def official_occurrence_expiration(event: dict, reference: date) -> dict | None:
    """Return provenance when a specific official URL disproves a derived schedule.

    A dated official occurrence is authoritative only for a single record: do
    not apply it to explicit occurrence series. Requiring the official page's
    completed-state text prevents arbitrary query parameters from suppressing
    otherwise valid future events.
    """
    schedule = event.get("schedule") if isinstance(event.get("schedule"), dict) else {}
    if schedule.get("occurrences"):
        return None
    url = source_url(event)
    try:
        parsed = urlparse(url)
        raw_date = (parse_qs(parsed.query).get("occurrence") or [""])[0]
        occurrence_date = date.fromisoformat(raw_date)
    except (TypeError, ValueError):
        return None
    if occurrence_date >= reference or not OFFICIAL_EXPIRED_TEXT.search(clean_html_text(event.get("description"))):
        return None
    scheduled = parse_schedule_date(schedule.get("start"))
    if scheduled == occurrence_date:
        return None
    return {
        "official_occurrence_date": occurrence_date.isoformat(),
        "source_url": url,
        "source_host": parsed.hostname,
        "scheduled_start": clean_space(schedule.get("start")) or None,
        "provenance": copy.deepcopy(event.get("provenance") or {}),
    }
def reference_date(dataset: dict) -> date | None:
    value = clean_space(dataset.get("publication_date"))
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _single_occurrence_display(start: object) -> str | None:
    value = clean_space(start)
    parsed = parse_schedule_date(value)
    if parsed is None:
        return None
    match = re.search(r"T(\d{2}:\d{2})", value)
    return f"{parsed.isoformat()} · {match.group(1)}" if match else parsed.isoformat()


def prune_expired_schedule(event: dict, reference: date) -> tuple[bool, list[dict]]:
    """Prune every past function and promote the first publishable one.

    ``schedule.start`` is the first function of a series, not an exemption from
    temporal pruning.  When it has passed, the first retained occurrence becomes
    the canonical start so a stale historical function cannot survive merely
    because of its representation.
    """
    schedule = copy.deepcopy(event.get("schedule") or {})
    occurrences = schedule.get("occurrences")
    removed: list[dict] = []

    if isinstance(occurrences, list) and occurrences:
        kept_occurrences = []
        for occurrence in occurrences:
            occurrence = occurrence or {}
            occurrence_end = parse_schedule_date(occurrence.get("end") or occurrence.get("start"))
            if occurrence_end is not None and occurrence_end < reference:
                removed.append(copy.deepcopy(occurrence))
                continue
            kept_occurrences.append(copy.deepcopy(occurrence))

        primary_end = parse_schedule_date(schedule.get("start"))
        if primary_end is not None and primary_end < reference:
            primary_start = clean_space(schedule.get("start"))
            if not any(clean_space(item.get("start")) == primary_start for item in removed):
                removed.insert(0, {
                    "start": schedule.get("start"),
                    "end": None,
                    "representation": "schedule.start",
                })
            if not kept_occurrences:
                return False, removed
            promoted = kept_occurrences[0]
            schedule["start"] = promoted.get("start")
            if promoted.get("end") not in (None, ""):
                schedule["end"] = promoted.get("end")
            elif len(kept_occurrences) == 1:
                schedule["end"] = None
            display = _single_occurrence_display(schedule.get("start"))
            if display:
                schedule["display_text"] = display
        schedule["occurrences"] = kept_occurrences
        event["schedule"] = schedule
        return True, removed

    end_date = parse_schedule_date(schedule.get("end"))
    start_date = parse_schedule_date(schedule.get("start"))
    effective_end = end_date or start_date
    if effective_end is not None and effective_end < reference:
        return False, removed
    return True, removed


def baseline_event_map(events: list[dict] | None) -> dict[str, dict] | None:
    if events is None:
        return None
    return {
        clean_space(event.get("id")): event
        for event in events
        if isinstance(event, dict) and clean_space(event.get("id"))
    }


def baseline_occurrence_map(events: list[dict] | None) -> dict[str, set[str]] | None:
    if events is None:
        return None
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for event in events:
        if not isinstance(event, dict):
            continue
        location = event.get("location") or {}
        key = (
            fold(event.get("title")),
            fold(location.get("city") or location.get("commune")),
            fold(location.get("venue_id") or location.get("venue")),
        )
        if all(key):
            groups[key].append(event)

    result: dict[str, set[str]] = {}
    for members in groups.values():
        for member in members:
            member_id = clean_space(member.get("id"))
            if member_id:
                rows: list[dict] = []
                for contributor in members:
                    schedule = contributor.get("schedule") or {}
                    # The canonical row's start remains the series boundary;
                    # starts contributed by aliases become canonical occurrences.
                    if contributor is not member and schedule.get("start"):
                        rows.append({"start": schedule.get("start"), "end": None})
                    rows.extend(
                        item for item in schedule.get("occurrences") or [] if isinstance(item, dict)
                    )
                result[member_id] = {occurrence_id(member, item) for item in rows}
    return result


def append_baseline_receipt(
    ledger: dict, receipt: dict, *, baseline_by_id: dict[str, dict] | None,
    occurrence_must_exist: bool = False,
    baseline_occurrences: dict[str, set[str]] | None = None,
) -> bool:
    """Append only receipts that explain a protected baseline transformation.

    With no baseline (unit-level callers), retain the historical behaviour.
    Candidate-only duplicates and quarantines remain in the private change
    report but cannot masquerade as public-baseline loss receipts.
    """
    if baseline_by_id is None:
        return append_receipt(ledger, receipt)
    source = baseline_by_id.get(clean_space(receipt.get("source_record_id")))
    if source is None:
        return False
    receipt = copy.deepcopy(receipt)
    receipt["source_url"] = source_url(source) or None
    receipt["title"] = source.get("title")
    receipt["provenance"] = copy.deepcopy(source.get("provenance") or {
        "source_url": source_url(source),
        "method": "public_baseline_record_provenance",
    })
    if occurrence_must_exist:
        evidence = receipt.get("evidence") if isinstance(receipt.get("evidence"), dict) else {}
        removed = evidence.get("occurrence") if isinstance(evidence.get("occurrence"), dict) else None
        if removed is not None:
            receipt["occurrence_id"] = occurrence_id(source, removed)
        known = (baseline_occurrences or {}).get(clean_space(receipt.get("source_record_id")), set())
        if clean_space(receipt.get("occurrence_id")) not in known:
            return False
    return append_receipt(ledger, receipt)


def refresh_counts(dataset: dict) -> None:
    events = dataset.get("events") or []
    counts = dict(dataset.get("counts") or {})
    counts["total"] = len(events)
    counts["events"] = sum(1 for event in events if event.get("event_type") == "event")
    counts["courses"] = sum(1 for event in events if event.get("event_type") == "course")
    counts["flexible_offers"] = sum(1 for event in events if event.get("event_type") == "flexible_offer")
    counts["programs"] = sum(1 for event in events if event.get("event_type") == "program")
    dataset["counts"] = counts


def exact_source_occurrence_key(event: dict) -> tuple[str, str, str, str, str] | None:
    """Identify duplicate records for one occurrence from one canonical source."""
    schedule = event.get("schedule") if isinstance(event.get("schedule"), dict) else {}
    location = event.get("location") if isinstance(event.get("location"), dict) else {}
    url = source_url(event)
    host = (urlparse(url).hostname or "").casefold() if url else ""
    source_identity = (
        host if host and host not in SOCIAL_HOSTS and host != "linktr.ee"
        else fold(event.get("source_id") or event.get("source_name"))
    )
    key = (
        source_identity,
        fold(event.get("title")),
        fold(location.get("city") or location.get("commune")),
        fold(location.get("venue")),
        clean_space(schedule.get("start")),
    )
    return key if all(key) else None


def venue_hours_contamination_reason(event: dict) -> str | None:
    """Do not use venue opening hours as an exhibition occurrence or end date."""
    schedule = event.get("schedule") if isinstance(event.get("schedule"), dict) else {}
    categories = {
        str(item.get("id")) for item in (event.get("categories") or [])
        if isinstance(item, dict)
    }
    has_venue_hours = bool(
        schedule.get("venue_hours")
        or (
            schedule.get("opening_time")
            and schedule.get("closing_time")
            and str(schedule.get("hours_confidence") or "").strip()
        )
    )
    semantic_text = fold(" ".join((
        clean_space(event.get("title")),
        clean_space(event.get("description")),
    )))
    is_long_running_exhibition = any(
        token in semantic_text
        for token in ("exposicion", "exhibicion", "muestra temporal", "muestra transitoria")
    )
    if (
        str(event.get("event_type") or "event") == "event"
        and "exposiciones" in categories
        and is_long_running_exhibition
        and has_venue_hours
        and schedule.get("start")
        and not schedule.get("end")
        and not schedule.get("occurrences")
    ):
        return "venue_hours_contaminated_event_schedule_missing_verified_end"
    return None


def consolidate_exact_source_occurrences(
    events: list[dict], *, ledger: dict, changes: dict[str, list],
    baseline_by_id: dict[str, dict] | None = None,
) -> list[dict]:
    groups: dict[tuple[str, str, str, str, str], list[dict]] = defaultdict(list)
    ungrouped: list[dict] = []
    for event in events:
        key = exact_source_occurrence_key(event)
        if key is None:
            ungrouped.append(event)
        else:
            groups[key].append(event)

    consolidated = list(ungrouped)
    for key, members in groups.items():
        if len(members) == 1:
            consolidated.extend(members)
            continue
        preferred = max(members, key=event_score)
        duplicates = [event for event in members if event is not preferred]
        for duplicate in duplicates:
            merge_missing(preferred, duplicate)
            append_baseline_receipt(ledger, make_receipt(
                stage="content_quality_guard", action="deduplication",
                reason="same_source_title_venue_city_and_start", source_event=duplicate,
                canonical_event_id=str(preferred.get("id") or ""),
                destination={"state": "merged", "canonical_event_id": preferred.get("id")},
                evidence={
                    "source_identity": key[0], "title": key[1], "city": key[2],
                    "venue": key[3], "start": key[4],
                },
                preserved_fields=[
                    field for field in (
                        "title", "description", "schedule", "location", "image", "price", "links", "primary_category"
                    ) if preferred.get(field) not in (None, "", [], {})
                ],
                combined_provenance={
                    "canonical": copy.deepcopy(preferred.get("provenance") or {}),
                    "duplicate": copy.deepcopy(duplicate.get("provenance") or {}),
                    "sources": sorted(filter(None, [source_url(preferred), source_url(duplicate)])),
                },
            ), baseline_by_id=baseline_by_id)
        changes["duplicates_consolidated"].append({
            "kind": "exact_source_occurrence",
            "kept_id": preferred.get("id"),
            "removed_ids": [event.get("id") for event in duplicates],
            "start": key[4],
        })
        consolidated.append(preferred)
    return consolidated


def apply_guard(
    dataset: dict, *, ledger: dict | None = None, generated_at: str | None = None,
    baseline_events: list[dict] | None = None,
) -> dict:
    before_semantic = semantic_payload(dataset)
    ledger = ledger if ledger is not None else empty_ledger(generated_at=dataset.get("generated_at"))
    events = list(dataset.get("events") or [])
    changes: dict[str, list] = {
        "html_cleaned": [],
        "titles_recovered": [],
        "duplicates_consolidated": [],
        "quarantined": [],
        "expired_removed": [],
        "past_occurrences_pruned": [],
    }
    baseline_by_id = baseline_event_map(baseline_events)
    baseline_occurrences = baseline_occurrence_map(baseline_events)
    events = consolidate_exact_source_occurrences(
        events, ledger=ledger, changes=changes, baseline_by_id=baseline_by_id
    )
    if generated_at:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        dataset["publication_date"] = generated.date().isoformat()
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

        materialize_submission_call(event)

        if is_non_event_title(event.get("title")):
            changes["quarantined"].append({
                "id": event_id,
                "title": event.get("title"),
                "reason": "calendar_navigation_or_empty_state",
            })
            append_baseline_receipt(ledger, make_receipt(
                stage="content_quality_guard", action="quarantine",
                reason="calendar_navigation_or_empty_state", source_event=event,
                canonical_event_id=None,
                destination={"state": "quarantine", "canonical_event_id": None},
            ), baseline_by_id=baseline_by_id)
            continue

        review = explicit_publication_review_reason(event)
        if review:
            review_reason, missing_evidence = review
            reason = f"upstream_publication_review:{review_reason}"
            changes["quarantined"].append({
                "id": event_id,
                "title": event.get("title"),
                "reason": reason,
                "missing_evidence": missing_evidence,
            })
            append_baseline_receipt(ledger, make_receipt(
                stage="content_quality_guard",
                action="quarantine",
                reason=reason,
                source_event=event,
                canonical_event_id=None,
                destination={"state": "quarantine", "canonical_event_id": None},
                evidence={"missing_evidence": missing_evidence},
            ), baseline_by_id=baseline_by_id)
            continue

        context_reason = non_event_context_reason(event)
        if context_reason:
            receipt = {
                "id": event_id,
                "title": event.get("title"),
                "reason": context_reason,
            }
            if context_reason == "multi_event_geography_conflict_with_truncated_segment":
                receipt["source_url"] = source_url(event)
                receipt["location"] = copy.deepcopy(event.get("location") or {})
                receipt["provenance"] = copy.deepcopy(event.get("provenance") or {})
            elif context_reason == "unverified_call_for_submissions_missing_official_bases":
                receipt["missing_evidence"] = submission_call_missing_evidence(event)
            changes["quarantined"].append(receipt)
            action = "non_event_exclusion" if context_reason == "promotional_giveaway_not_attendance_event" else "quarantine"
            append_baseline_receipt(ledger, make_receipt(
                stage="content_quality_guard", action=action, reason=context_reason,
                source_event=event, canonical_event_id=None,
                destination={"state": action, "canonical_event_id": None},
                evidence={key: value for key, value in receipt.items() if key not in {"id", "title", "reason"}},
            ), baseline_by_id=baseline_by_id)
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
            missing = [
                field for field, value in (
                    ("recoverable_title", None),
                    ("description", clean_html_text(event.get("description"))),
                    ("venue", clean_space((event.get("location") or {}).get("venue"))),
                    ("occurrence", (event.get("schedule") or {}).get("start")),
                ) if not value
            ]
            changes["quarantined"].append({
                "id": event_id, "title": event.get("title"),
                "reason": "generic_title_without_explicit_recovery", "missing_evidence": missing,
            })
            append_baseline_receipt(ledger, make_receipt(
                stage="content_quality_guard", action="quarantine",
                reason="generic_title_without_explicit_recovery", source_event=event,
                canonical_event_id=None,
                destination={"state": "quarantine", "canonical_event_id": None},
                evidence={"missing_evidence": missing},
            ), baseline_by_id=baseline_by_id)
            continue

        if publication_day is not None:
            contamination_reason = venue_hours_contamination_reason(event)
            if contamination_reason:
                evidence = {
                    "schedule": copy.deepcopy(event.get("schedule") or {}),
                    "source_url": source_url(event),
                    "missing_evidence": ["verified_event_end_date_or_occurrence"],
                }
                changes["quarantined"].append({
                    "id": event_id,
                    "title": event.get("title"),
                    "reason": contamination_reason,
                    "missing_evidence": evidence["missing_evidence"],
                })
                append_baseline_receipt(ledger, make_receipt(
                    stage="content_quality_guard",
                    action="quarantine",
                    reason=contamination_reason,
                    source_event=event,
                    canonical_event_id=event_id,
                    destination={"state": "quarantine", "canonical_event_id": event_id},
                    evidence=evidence,
                ), baseline_by_id=baseline_by_id)
                continue
            official_expiration = official_occurrence_expiration(event, publication_day)
            if official_expiration:
                changes["expired_removed"].append({
                    "id": event_id,
                    "title": event.get("title"),
                    "reason": "official_occurrence_expired_schedule_conflict",
                    **official_expiration,
                })
                append_baseline_receipt(ledger, make_receipt(
                    stage="content_quality_guard", action="expiration",
                    reason="official_occurrence_expired_schedule_conflict", source_event=event,
                    canonical_event_id=None,
                    destination={"state": "expired", "canonical_event_id": None},
                    evidence=official_expiration,
                ), baseline_by_id=baseline_by_id)
                continue
            keep, removed_moments = prune_expired_schedule(event, publication_day)
            if not keep:
                changes["expired_removed"].append({
                    "id": event_id,
                    "title": event.get("title"),
                    "reason": "schedule_ended_before_publication_date",
                })
                append_baseline_receipt(ledger, make_receipt(
                    stage="content_quality_guard", action="expiration",
                    reason="schedule_ended_before_publication_date", source_event=event,
                    canonical_event_id=None,
                    destination={"state": "expired", "canonical_event_id": None},
                ), baseline_by_id=baseline_by_id)
                continue
            if removed_moments:
                removed_occurrences = removed_moments
                changes["past_occurrences_pruned"].append({
                    "id": event_id, "count": len(removed_occurrences),
                    "occurrence_ids": [occurrence_id(event, item) for item in removed_occurrences],
                })
                for removed_occurrence in removed_occurrences:
                    append_baseline_receipt(ledger, make_receipt(
                        stage="content_quality_guard", action="occurrence_pruning",
                        reason="past_occurrence_pruned_from_active_series", source_event=event,
                        canonical_event_id=event_id,
                        destination={"state": "series_preserved", "canonical_event_id": event_id},
                        evidence={"occurrence": removed_occurrence},
                        occurrence=removed_occurrence,
                    ), baseline_by_id=baseline_by_id, occurrence_must_exist=True,
                        baseline_occurrences=baseline_occurrences)

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
            preserved = [
                field for field in ("title", "description", "schedule", "location", "image", "price", "links", "primary_category")
                if preferred.get(field) not in (None, "", [], {})
            ]
            append_baseline_receipt(ledger, make_receipt(
                stage="content_quality_guard", action="deduplication",
                reason="same_venue_title_and_occurrence", source_event=duplicate,
                canonical_event_id=str(preferred.get("id") or ""),
                destination={"state": "merged", "canonical_event_id": preferred.get("id")},
                evidence={
                    "same_venue": key,
                    "same_canonical_title": canonical,
                    "source_occurrence_id": occurrence_id(duplicate),
                    "canonical_occurrence_id": occurrence_id(preferred),
                },
                preserved_fields=preserved,
                combined_provenance={
                    "canonical": copy.deepcopy(preferred.get("provenance") or {}),
                    "duplicate": copy.deepcopy(duplicate.get("provenance") or {}),
                    "sources": sorted(filter(None, [source_url(preferred), source_url(duplicate)])),
                },
            ), baseline_by_id=baseline_by_id)
        changes["duplicates_consolidated"].append({
            "venue_key": key,
            "canonical_title": canonical,
            "kept_id": preferred.get("id"),
            "removed_ids": [event.get("id") for event in duplicates],
        })

    dataset["events"] = [event for event in sanitized if str(event.get("id") or "") not in removed_ids]
    refresh_counts(dataset)
    if semantic_payload(dataset) != before_semantic:
        dataset["generated_at"] = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
        ledger["generated_at"] = dataset["generated_at"]
    changes["receipt_ledger"] = ledger
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


def sanitize_dataset(
    dataset_path: Path,
    *,
    ledger: dict | None = None,
    generated_at: str | None = None,
    baseline_events: list[dict] | None = None,
) -> tuple[dict, dict]:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    before = len(dataset.get("events") or [])
    changes = apply_guard(
        dataset, ledger=ledger, generated_at=generated_at, baseline_events=baseline_events
    )
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


def git_baseline_events(dataset_path: Path) -> list[dict]:
    """Read the immutable checkout baseline without relying on a temp copy."""
    relative = dataset_path.resolve().relative_to(ROOT.resolve()).as_posix()
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"HEAD:{relative}"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(completed.stdout)
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError(f"Git baseline has no events array: {relative}")
    return [event for event in events if isinstance(event, dict)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitize public content, dates, titles and duplicate exhibitions.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--all-cities", action="store_true", help="Apply the same guard to every dataset registered in app/cities.json.")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--new-ledger", action="store_true")
    parser.add_argument("--generated-at")
    parser.add_argument(
        "--baseline", type=Path,
        help="Optional immutable public baseline; defaults to the dataset blob at Git HEAD.",
    )
    args = parser.parse_args()

    report_path = Path(args.report)
    targets = configured_datasets() if args.all_cities else [("dataset", Path(args.dataset))]
    city_reports: list[dict] = []
    sanitized_payloads: list[tuple[Path, dict]] = []

    ledger = empty_ledger() if args.new_ledger else load_ledger(args.ledger)
    for city_id, dataset_path in targets:
        if args.baseline:
            baseline_payload = json.loads(args.baseline.read_text(encoding="utf-8"))
            baseline_events = baseline_payload.get("events") or []
        else:
            baseline_events = git_baseline_events(dataset_path)
        dataset, report = sanitize_dataset(
            dataset_path, ledger=ledger, generated_at=args.generated_at,
            baseline_events=baseline_events,
        )
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
        writes = [
            (path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            for path, payload in sanitized_payloads
        ]
        writes.extend([
            (report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n"),
            (args.ledger, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n"),
        ])
        staged: list[tuple[Path, Path]] = []
        try:
            for path, content in writes:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(path.name + ".tmp")
                temporary.write_text(content, encoding="utf-8", newline="\n")
                staged.append((temporary, path))
            for temporary, path in staged:
                os.replace(temporary, path)
        finally:
            for temporary, _path in staged:
                temporary.unlink(missing_ok=True)

    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
