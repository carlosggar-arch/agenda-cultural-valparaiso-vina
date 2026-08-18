from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "app/data/quality/priority-zero-monitors.json"
TIMEZONE = "America/Santiago"

TARGETS = (
    {
        "id": "balmaceda_arte_joven_valpo",
        "name": "Balmaceda Arte Joven Valparaíso",
        "url": "https://www.balmacedartejoven.cl/",
        "detector": "baj_valpo",
        "evidence": "official_site",
    },
    {
        "id": "sala_teatro_ipa",
        "name": "Sala Teatro IPA",
        "url": "https://telonticket.cl/mep_cat/performance/",
        "detector": "sala_ipa",
        "evidence": "specialized_theatre_calendar",
    },
    {
        "id": "teatro_la_peste",
        "name": "Teatro La Peste",
        "url": "https://ticketplus.cl/companies/teatro-la-peste",
        "detector": "teatro_la_peste",
        "evidence": "official_ticketing_company_page",
    },
)

MONTHS = {
    "enero": 1, "ene": 1,
    "febrero": 2, "feb": 2,
    "marzo": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6,
    "julio": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "septiembre": 9, "sept": 9, "sep": 9,
    "octubre": 10, "oct": 10,
    "noviembre": 11, "nov": 11,
    "diciembre": 12, "dic": 12,
}
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_PATTERNS = (
    re.compile(rf"\b(\d{{1,2}})\s+(?:de\s+)?({MONTH_PATTERN})(?:\s+de)?\s+(20\d{{2}})\b", re.I),
    re.compile(rf"\b({MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(20\d{{2}})\b", re.I),
    re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b"),
)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.casefold()).strip()


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
            return
        if not self.skip and tag in {"br", "p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "time", "td", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag) -> None:
        if tag in {"script", "style", "noscript"}:
            if self.skip:
                self.skip -= 1
            return
        if not self.skip and tag in {"p", "div", "li", "article", "section", "h1", "h2", "h3", "h4", "time", "td", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data) -> None:
        if not self.skip:
            self.parts.append(data)

    def lines(self) -> list[str]:
        text = html.unescape("".join(self.parts)).replace("\xa0", " ")
        return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def text_lines(markup: str) -> list[str]:
    parser = TextParser()
    parser.feed(markup)
    return parser.lines()


def fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310 - fixed HTTPS sources
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                markup = raw.decode(charset, errors="replace")
            except LookupError:
                markup = raw.decode("utf-8", errors="replace")
            return True, getattr(response, "status", 200), markup, None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def explicit_dates(text: str) -> list[date]:
    found: list[date] = []
    for index, pattern in enumerate(DATE_PATTERNS):
        for match in pattern.finditer(norm(text)):
            try:
                if index == 0:
                    day = int(match.group(1))
                    month = MONTHS[match.group(2)]
                    year = int(match.group(3))
                elif index == 1:
                    month = MONTHS[match.group(1)]
                    day = int(match.group(2))
                    year = int(match.group(3))
                else:
                    day = int(match.group(1))
                    month = int(match.group(2))
                    year = int(match.group(3))
                value = date(year, month, day)
            except (ValueError, KeyError):
                continue
            if value not in found:
                found.append(value)
    return sorted(found)


def context_window(lines: list[str], index: int, radius: int = 3) -> str:
    return " ".join(lines[max(0, index - radius): min(len(lines), index + radius + 1)])


def detect_baj_valpo(lines: list[str], today: date) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        context = context_window(lines, index, radius=4)
        normalized = norm(context)
        if "valparaiso" not in normalized and "baj valpo" not in normalized:
            continue
        if not any(token in normalized for token in ("taller", "expos", "program", "actividad", "inscrip", "present", "funcion")):
            continue
        for value in explicit_dates(context):
            if value < today:
                continue
            signature = value.isoformat() + "|" + normalized[:160]
            if signature in seen:
                continue
            seen.add(signature)
            candidates.append({"date": value.isoformat(), "context": context[:360]})
    return candidates


def detect_sala_ipa(lines: list[str], today: date) -> list[dict]:
    candidates: list[dict] = []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        if "sala teatro ipa" not in norm(line):
            continue
        context = context_window(lines, index, radius=4)
        for value in explicit_dates(context):
            if value < today:
                continue
            signature = value.isoformat() + "|" + norm(context)[:160]
            if signature in seen:
                continue
            seen.add(signature)
            candidates.append({"date": value.isoformat(), "context": context[:360]})
    return candidates


def detect_teatro_la_peste(lines: list[str], today: date) -> tuple[list[dict], bool]:
    combined = " ".join(lines)
    normalized = norm(combined)
    explicit_empty = "no hay eventos disponibles" in normalized
    candidates = [
        {"date": value.isoformat(), "context": combined[:360]}
        for value in explicit_dates(combined)
        if value >= today
    ]
    return candidates, explicit_empty


def classify(target: dict, markup: str, today: date) -> dict:
    lines = text_lines(markup)
    detector = target["detector"]
    explicit_empty = False
    if detector == "baj_valpo":
        candidates = detect_baj_valpo(lines, today)
    elif detector == "sala_ipa":
        candidates = detect_sala_ipa(lines, today)
    elif detector == "teatro_la_peste":
        candidates, explicit_empty = detect_teatro_la_peste(lines, today)
    else:
        raise ValueError(f"Unknown priority-zero detector: {detector}")

    if candidates:
        state = "future_detected"
    elif detector == "teatro_la_peste" and not explicit_empty:
        state = "indeterminate"
    else:
        state = "verified_no_publishable_future"

    return {
        "id": target["id"],
        "name": target["name"],
        "url": target["url"],
        "evidence": target["evidence"],
        "state": state,
        "verified_inactive": state == "verified_no_publishable_future",
        "future_candidates": candidates,
        "future_candidates_count": len(candidates),
        "explicit_empty_state": explicit_empty,
    }


def build() -> dict:
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    rows = []
    for target in TARGETS:
        ok, status, markup, error = fetch(target["url"])
        if ok:
            row = classify(target, markup, today)
            row.update({"fetch_ok": True, "http_status": status, "error": None})
        else:
            row = {
                "id": target["id"],
                "name": target["name"],
                "url": target["url"],
                "evidence": target["evidence"],
                "state": "fetch_error",
                "verified_inactive": False,
                "future_candidates": [],
                "future_candidates_count": 0,
                "explicit_empty_state": False,
                "fetch_ok": False,
                "http_status": status,
                "error": error,
            }
        rows.append(row)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "timezone": TIMEZONE,
        "date": today.isoformat(),
        "state": "ok" if all(row["fetch_ok"] for row in rows) else "partial",
        "verified_inactive_count": sum(row["verified_inactive"] for row in rows),
        "future_detected_count": sum(row["state"] == "future_detected" for row in rows),
        "sources": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify whether priority Valparaiso zero sources have publishable future programming.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report = build()
    if args.no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": report["state"],
        "verified_inactive_count": report["verified_inactive_count"],
        "future_detected_count": report["future_detected_count"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
