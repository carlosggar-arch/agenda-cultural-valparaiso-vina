from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "agenda_web.json"

QUOTE_PATTERNS = (
    re.compile(r"“([^”]{3,140})”"),
    re.compile(r'"([^"\n]{3,140})"'),
    re.compile(r"«([^»]{3,140})»"),
)

ACTIVITY_TERMS = re.compile(
    r"\b(?:exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla|conversatorio|"
    r"funci[oó]n|espect[aá]culo|presentaci[oó]n|encuentro|visita guiada|seminario|curso)\b",
    re.I,
)

FOLLOWING_TITLE_VERBS = re.compile(
    r"^\s*(?:lleg[oóa]|llega|se presenta|se exhibe|se inaugura|se realizar[aá]|se realiza|"
    r"se presentar[aá]|se podr[aá] ver|abre|estar[aá]|vuelve)\b",
    re.I,
)

EXHIBITION_TERMS = re.compile(r"\b(?:exposici[oó]n|muestra)\b", re.I)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_candidate(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text.rstrip(" .,:;–—-").strip()


def suspicious_venue_title(event: dict) -> bool:
    title = norm(event.get("title"))
    if not title:
        return False
    location = event.get("location") or {}
    venue = norm(location.get("venue"))
    city = norm(location.get("city"))
    source = norm(event.get("source_name"))
    organizer = norm(event.get("organizer"))

    if venue and title == venue:
        return True
    if venue and city and title in {f"{venue} {city}", f"{city} {venue}"}:
        return True
    # Some publishers expose the venue as both source and title. Treat that as
    # suspicious only when it is also the location, so artist/organization names
    # that legitimately name an event are not rewritten.
    if venue and source and title == source == venue:
        return True
    if venue and organizer and title == organizer == venue:
        return True
    return False


def _candidate_score(description: str, match: re.Match[str], event: dict) -> int:
    candidate = clean_candidate(match.group(1))
    candidate_norm = norm(candidate)
    if not candidate_norm:
        return -100

    venue_norm = norm((event.get("location") or {}).get("venue"))
    source_norm = norm(event.get("source_name"))
    organizer_norm = norm(event.get("organizer"))
    if candidate_norm in {venue_norm, source_norm, organizer_norm}:
        return -100

    words = candidate_norm.split()
    if not (2 <= len(words) <= 16):
        return -100
    if re.search(r"https?://|www\.", candidate, re.I):
        return -100

    score = 0
    after = description[match.end(): match.end() + 80]
    around = description[max(0, match.start() - 120): match.end() + 160]
    before = description[max(0, match.start() - 70): match.start()]

    if FOLLOWING_TITLE_VERBS.search(after):
        score += 4
    if ACTIVITY_TERMS.search(around):
        score += 2
    if re.search(r"(?:exposici[oó]n|muestra|obra|concierto|recital|festival|taller|charla)\s*(?:titulada?|llamada?)?\s*$", before, re.I):
        score += 4
    if match.start() <= 12:
        score += 1
    if 2 <= len(words) <= 10:
        score += 1
    return score


def recover_explicit_title(event: dict) -> tuple[str | None, str | None]:
    if not suspicious_venue_title(event):
        return None, None
    description = str(event.get("description") or "").strip()
    if not description:
        return None, None

    candidates: list[tuple[int, int, str]] = []
    for pattern in QUOTE_PATTERNS:
        for match in pattern.finditer(description):
            score = _candidate_score(description, match, event)
            if score >= 5:
                candidates.append((score, -match.start(), clean_candidate(match.group(1))))

    if not candidates:
        return None, None
    candidates.sort(reverse=True)
    return candidates[0][2], "explicit_quoted_activity_in_description"


def infer_category(event: dict, recovered_title: str) -> tuple[str, str] | None:
    description = str(event.get("description") or "")
    evidence = f"{recovered_title} {description[:500]}"
    if EXHIBITION_TERMS.search(evidence):
        return "exposiciones", "Exposiciones"
    return None


def apply_guard(dataset: dict) -> list[dict]:
    changes: list[dict] = []
    for event in dataset.get("events") or []:
        recovered, reason = recover_explicit_title(event)
        if not recovered or not reason:
            continue

        old_title = str(event.get("title") or "").strip()
        if norm(old_title) == norm(recovered):
            continue

        event["title"] = recovered
        editorial = dict(event.get("editorial") or {})
        editorial.setdefault("title_original", old_title)
        editorial["title_recovered"] = True
        editorial["title_recovery_reason"] = reason
        event["editorial"] = editorial

        category_change = None
        inferred = infer_category(event, recovered)
        if inferred:
            category_id, category_label = inferred
            old_category = dict(event.get("primary_category") or {})
            if old_category.get("id") != category_id:
                event["primary_category"] = {"id": category_id, "label": category_label}
                event["categories"] = [{"id": category_id, "label": category_label}]
                category_change = {
                    "from": old_category,
                    "to": {"id": category_id, "label": category_label},
                }
                editorial["category_recovered_from_title_context"] = True

        changes.append({
            "id": event.get("id"),
            "from": old_title,
            "to": recovered,
            "reason": reason,
            "category_change": category_change,
        })
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover activity titles accidentally replaced by venue names.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    path = Path(args.dataset)
    dataset = json.loads(path.read_text(encoding="utf-8"))
    changes = apply_guard(dataset)

    if changes and not args.no_write:
        path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "dataset": str(path),
        "changes": changes,
        "changed_count": len(changes),
        "write": bool(changes and not args.no_write),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
