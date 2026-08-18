from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import refresh_balmaceda_valpo as core

MAX_LINKS_PER_LANDING = 2
HTTP_TIMEOUT_SECONDS = 6
LEAD_BLOCKS = 8
STRONG_VALPO_MARKERS = (
    "baj valpo",
    "sede valparaiso",
    "santa isabel 739",
    "cerro alegre",
    "galeria balmaceda arte joven valparaiso",
)


def bounded_fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # nosec B310 - official configured HTTPS URLs
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return True, getattr(response, "status", 200), text, None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def bounded_discover(markup: str) -> list[str]:
    return core.discover_links(markup)[:MAX_LINKS_PER_LANDING]


def safe_valpo_page(url: str, parser: core.PageParser) -> bool:
    path = urlparse(url).path.casefold()
    if "/noticias/" in path:
        if "/noticias/valparaiso/" in path:
            return True
        if any(region in path for region in ("/biobio/", "/antofagasta/", "/metropolitana/", "/los-lagos/")):
            return False
    lead = core.norm(" ".join(parser.parts[:LEAD_BLOCKS]))
    return any(marker in lead for marker in STRONG_VALPO_MARKERS)


def prior_report() -> dict:
    if not core.REPORT_PATH.exists():
        return {}
    try:
        return json.loads(core.REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def run(no_write: bool = False) -> int:
    today = datetime.now(ZoneInfo(core.TIMEZONE)).date()
    dataset = json.loads(core.DATASET_PATH.read_text(encoding="utf-8"))
    original = list(dataset.get("events") or [])
    previous = [
        item for item in original
        if str((item.get("editorial") or {}).get("reason") or "") == "official_source:balmaceda_arte_joven_valpo"
        and str((item.get("schedule") or {}).get("end") or (item.get("schedule") or {}).get("start") or "")[:10] >= today.isoformat()
    ]
    base = [
        item for item in original
        if str((item.get("editorial") or {}).get("reason") or "") != "official_source:balmaceda_arte_joven_valpo"
    ]

    landing_results = []
    links: list[str] = []
    seen: set[str] = set()
    for url in core.LANDING_URLS:
        ok, status, markup, error = bounded_fetch(url)
        landing_results.append({"url": url, "fetch_ok": ok, "http_status": status, "error": error})
        if ok:
            for link in bounded_discover(markup):
                if link not in seen:
                    seen.add(link)
                    links.append(link)

    site_reachable = any(item["fetch_ok"] for item in landing_results)
    discovery_confident = site_reachable and bool(links)
    recent_pages = 0
    scanned = 0
    failures = []
    fresh: list[dict] = []
    recent_titles: list[str] = []
    cutoff = today - timedelta(days=180)

    for url in links:
        ok, status, markup, error = bounded_fetch(url)
        if not ok:
            failures.append({"url": url, "http_status": status, "error": error})
            continue
        scanned += 1
        parser = core.parse(markup)
        published = core.as_published_day(parser)
        title = parser.h1 or (parser.parts[0] if parser.parts else "")
        local_page = safe_valpo_page(url, parser)
        if local_page and published and published >= cutoff:
            recent_pages += 1
            if title:
                recent_titles.append(title)
        if not local_page or not title:
            continue
        image = parser.meta.get("og:image")
        for start, end, clock, block in core.same_block_candidates(parser, today):
            fresh.append(core.make_event(title, start, end, clock, url, image, block))

    pool = fresh if discovery_confident else previous + fresh
    source_events = []
    duplicates = 0
    ids: set[str] = set()
    for candidate in pool:
        candidate_id = str(candidate.get("id") or "")
        if not candidate_id or candidate_id in ids:
            continue
        ids.add(candidate_id)
        if core.duplicate(candidate, base + source_events):
            duplicates += 1
            continue
        source_events.append(candidate)

    dataset["events"] = sorted(
        base + source_events,
        key=lambda item: (str((item.get("schedule") or {}).get("start") or ""), str(item.get("title") or "")),
    )
    core.refresh_counts(dataset)

    official_recent_activity = recent_pages > 0 or bool(source_events)
    previous_report = prior_report()
    if discovery_confident and source_events:
        state = "publishing_explicit_future_events"
    elif discovery_confident and official_recent_activity:
        state = "official_recent_activity_no_publishable_future_dates"
    elif discovery_confident:
        state = "official_site_checked_no_recent_activity_detected"
    elif site_reachable:
        state = "official_site_reachable_discovery_inconclusive"
    elif previous:
        state = "official_site_fetch_error_previous_events_preserved"
    else:
        state = "official_site_fetch_error"

    if discovery_confident:
        coverage = ([{
            "source_id": core.COVERED_SOURCE_ID,
            "source_name": core.SOURCE_NAME,
            "covered_by": core.SOURCE_ID,
            "reason": "official_recent_activity",
        }] if official_recent_activity else [])
    else:
        coverage = previous_report.get("coverage") or []

    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(ZoneInfo(core.TIMEZONE)).isoformat(timespec="seconds"),
        "source_id": core.SOURCE_ID,
        "source_name": core.SOURCE_NAME,
        "covered_source_id": core.COVERED_SOURCE_ID,
        "source_role": "official_primary_source",
        "state": state,
        "network_policy": {"timeout_seconds": HTTP_TIMEOUT_SECONDS, "max_links_per_landing": MAX_LINKS_PER_LANDING},
        "landings": landing_results,
        "links_discovered": len(links),
        "pages_scanned": scanned,
        "page_fetch_failures": failures,
        "recent_valpo_pages": recent_pages,
        "recent_valpo_titles": recent_titles[:12],
        "future_dated_candidates": len(fresh),
        "previous_future_events": len(previous),
        "events_published": len(source_events),
        "semantic_duplicates_dropped": duplicates,
        "coverage": coverage,
        "policy": "Recent coverage requires a Valparaiso-specific news path or strong Valparaiso context in leading content blocks; global footer text never counts. Event publication additionally requires an explicit future date and BAJ Valpo context in the same content block. Historical pages never create current events.",
    }

    if no_write:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        core.DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        core.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        core.REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Balmaceda official refresh with strict network and geography bounds.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(args.no_write))


if __name__ == "__main__":
    main()
