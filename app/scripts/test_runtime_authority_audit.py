from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def function_body(source: str, name: str) -> str:
    marker = f"function {name}("
    start = source.find(marker)
    if start < 0:
        raise AssertionError(f"Missing function {name}")
    brace = source.find("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:index + 1]
    raise AssertionError(f"Unclosed function {name}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    core = read("app/app-core.js")
    combined = read("app/combined-filters.js")
    schedule = read("assets/event-schedule-display.mjs")
    category = read("app/public-category-rules.mjs")
    order = read("app/agenda-order-core.mjs")
    visibility = read("app/visibility-owner-core.mjs")
    semantic_search = read("app/semantic-search.mjs")

    # Schedule: one canonical formatter. app-core may keep only its exhibition
    # wording wrapper and must delegate every ordinary schedule to the shared owner.
    schedule_wrapper = function_body(core, "formatSchedule")
    require(
        'formatSchedule as formatSharedSchedule' in core
        and '../assets/event-schedule-display.mjs' in core,
        "app-core must import the canonical shared schedule formatter",
    )
    require("formatSharedSchedule(" in schedule_wrapper, "app-core schedule wrapper must delegate ordinary schedules")
    require("Intl.DateTimeFormat" not in schedule_wrapper, "app-core schedule wrapper must not implement a second clock/date formatter")
    require("export function formatSchedule(" in schedule, "shared schedule module must expose the canonical formatter")

    # Category: taxonomy rules own normalization/classification. Renderers consume it.
    require("export function classifyPublicCategory(" in category, "taxonomy classifier authority disappeared")
    require("canonicalPublicCategory" in core, "app-core must consume canonical category aliases")
    require("canonicalPublicCategory" in combined, "combined filters must consume canonical category aliases")
    for source, label in ((core, "app-core"), (combined, "combined-filters")):
        require(
            not re.search(r"(?:MUSEUM_CATEGORY_ID|CATEGORY_ALIASES|CATEGORY_MAP)\s*=", source),
            f"{label} must not own a parallel category map",
        )

    # Semantic dimensions enrich search only. They must not become another filter
    # or category authority and weak candidates must never be indexed wholesale.
    search_body = function_body(core, "eventSearchHaystack")
    category_filter_body = function_body(core, "eventMatchesCategory")
    require("semanticSearchTerms" in core and "semantic-search.mjs" in core, "app-core must consume shared semantic search terms")
    require("semanticSearchTerms(event)" in search_body, "event search haystack must include orthogonal semantic terms")
    require("semanticSearchTerms" not in category_filter_body, "semantic dimensions must not alter the primary category filter")
    require("secondary_domains" in semantic_search, "semantic search must consume promoted secondary domains")
    require("promotedDomains.has" in semantic_search, "semantic search must reject weak non-promoted category candidates")

    # Temporal/order: agenda-order consumes, but never recreates, temporal vocabularies.
    require("temporal-priority-core.mjs" in order, "agenda order must consume temporal-priority-core")
    require("classifyTemporalEvent(" in order, "agenda order must use canonical temporal classification")
    require("eventDateRanges(" in order, "agenda order must use canonical temporal ranges")
    require(
        not re.search(r"(?:const|let|var)\s+(?:TEMPORAL_BUCKETS|CONTENT_KINDS)\s*=", order),
        "agenda order must not redeclare temporal vocabularies",
    )

    # Visibility: one decision core and one UI writer. Presentation enhancers may
    # request reconciliation but cannot maintain their own independent hide policy.
    require("shouldSuppressForTemporalFilter" in visibility, "visibility decision authority disappeared")
    require("visibility-owner-core.mjs" in combined, "combined filters must consume visibility-owner-core")
    require("card.hidden" in combined, "combined filters must remain the top-level visibility writer")
    for relative in (
        "app/temporal-priority.js",
        "app/exhibition-presentation-guard.js",
        "app/public-presentation-guard.js",
        "app/schedule-display.js",
        "app/exhibition-hours.js",
    ):
        source = read(relative)
        require(not re.search(r"\.hidden\s*=", source), f"{relative} must not become a second visibility writer")

    print("RUNTIME_AUTHORITY_AUDIT_OK schedule=shared category=shared semantic-search=isolated temporal=shared visibility=single-writer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
