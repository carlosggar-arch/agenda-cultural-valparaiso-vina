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

import generate_event_pages as generator  # noqa: E402


def read_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def current_artifacts() -> Iterator[tuple[Path, str, str]]:
    """Yield artifacts for current canonical events only.

    Historical permanent routes are intentionally outside this iteration: the
    contract requires every event in the current public datasets to have an
    exact canonical page, but it does not delete or reject older immutable
    routes that are no longer present in the live agenda.
    """
    event_urls: list[str] = []

    for city_id, city in generator.CITY_CONFIG.items():
        dataset_path: Path = city["dataset"]
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
        events = payload.get("events") or []
        if not isinstance(events, list):
            raise SystemExit(f"Invalid events array: {dataset_path}")

        stamp = generator.generated_at(payload)
        changes = generator.load_recent_changes(city.get("changes"), stamp)
        excluded = generator.CITY_EXCLUDED_IDS.get(city_id, set())

        for event in events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or "")
            if event_id in excluded:
                continue

            slug = generator.event_slug(event_id)
            relative = Path("evento") / city_id / slug
            event_url = generator.page_url(city_id, event)
            page, ics = generator.render_page(
                city_id,
                city,
                event,
                changes.get(event_id, []),
                stamp,
            )
            event_urls.append(event_url)
            yield ROOT / relative / "index.html", page, f"{city_id}/{event_id}/index.html"
            if ics is not None:
                yield ROOT / relative / "evento.ics", ics, f"{city_id}/{event_id}/evento.ics"

    yield generator.SITEMAP, generator.render_sitemap(event_urls), "sitemap.xml"


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
            "Permanent event pages are not canonical. Regenerate with "
            "`python scripts/generate_event_pages.py` and commit the resulting "
            f"current-event artifacts.\n\n{preview}{suffix}"
        )

    print(f"PERMANENT_EVENT_PAGE_CANONICAL_PARITY_OK artifacts={checked}")


if __name__ == "__main__":
    main()
