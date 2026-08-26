from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import stage31_site_generator as stage31  # noqa: E402

base = stage31.base


def read_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def current_artifacts() -> Iterator[tuple[Path, str, str]]:
    """Yield final Stage 3.1 artifacts for current canonical events only.

    Historical permanent routes are intentionally outside this iteration: the
    contract requires every event in the current public datasets to have an
    exact canonical page, but it does not delete or reject older immutable
    routes that are no longer present in the live agenda.
    """
    event_entries: list[tuple[str, str | None]] = []
    city_lastmod: dict[str, str | None] = {}
    city_payloads: dict[str, dict] = {}
    city_events: dict[str, list[dict]] = {}

    for city_id, city in base.CITY_CONFIG.items():
        dataset_path: Path = city["dataset"]
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        events = payload.get("events") or []
        if not isinstance(events, list):
            raise SystemExit(f"Invalid events array: {dataset_path}")

        stamp = base.generated_at(payload)
        lastmod = stage31._lastmod(payload)
        changes = base.load_recent_changes(city.get("changes"), stamp)
        excluded = base.CITY_EXCLUDED_IDS.get(city_id, set())
        current = [
            event
            for event in events
            if isinstance(event, dict) and str(event.get("id") or "") not in excluded
        ]
        city_lastmod[city_id] = lastmod
        city_payloads[city_id] = payload
        city_events[city_id] = current

        for event in current:
            event_id = str(event.get("id") or "")
            slug = base.event_slug(event_id)
            relative = Path("evento") / city_id / slug
            event_url = base.page_url(city_id, event)
            page, ics = stage31.enhance_event_page(
                city_id,
                city,
                event,
                changes.get(event_id, []),
                stamp,
            )
            event_entries.append((event_url, lastmod))
            yield ROOT / relative / "index.html", page, f"{city_id}/{event_id}/index.html"
            if ics is not None:
                yield ROOT / relative / "evento.ics", ics, f"{city_id}/{event_id}/evento.ics"

    root_landing = stage31.render_root_landing(
        city_payloads["valparaiso"], city_events["valparaiso"]
    )
    gijon_landing = stage31.render_city_landing(
        "gijon",
        base.CITY_CONFIG["gijon"],
        city_payloads["gijon"],
        city_events["gijon"],
    )
    sitemap = stage31.render_sitemap(event_entries, city_lastmod)
    yield ROOT / "index.html", root_landing, "index.html"
    yield ROOT / "gijon" / "index.html", gijon_landing, "gijon/index.html"
    yield stage31.SITEMAP, sitemap, "sitemap.xml"


def short_diff(actual: str, expected: str, label: str) -> str:
    rows = list(
        difflib.unified_diff(
            actual.splitlines(),
            expected.splitlines(),
            fromfile=f"committed/{label}",
            tofile=f"canonical/{label}",
            lineterm="",
            n=2,
        )
    )
    return "\n".join(rows[:24])


def main() -> None:
    mismatches: list[str] = []
    checked = 0

    for path, expected, label in current_artifacts():
        checked += 1
        if not path.exists():
            mismatches.append(f"MISSING {label}")
            continue
        actual = read_exact(path)
        if actual != expected:
            detail = short_diff(actual, expected, label)
            mismatches.append(f"STALE {label}\n{detail}".rstrip())

    if mismatches:
        preview = "\n\n".join(mismatches[:12])
        extra = len(mismatches) - 12
        suffix = f"\n\n... and {extra} more mismatches" if extra > 0 else ""
        raise SystemExit(
            "Permanent event pages are not canonical after the final Stage 3.1 writer. "
            "Regenerate with `python scripts/generate_event_pages.py` followed by "
            "`python scripts/stage31_site_generator.py` and commit the resulting "
            f"current-event artifacts.\n\n{preview}{suffix}"
        )

    print(f"PERMANENT_EVENT_PAGE_CANONICAL_PARITY_OK artifacts={checked}")


if __name__ == "__main__":
    main()
