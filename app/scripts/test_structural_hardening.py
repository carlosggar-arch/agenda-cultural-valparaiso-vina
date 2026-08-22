from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

release_text = (APP / "release-version.js").read_text(encoding="utf-8")
release_match = re.search(r"const\s+RELEASE\s*=\s*(\d+)\s*;", release_text)
assert release_match, "release-version.js must expose a numeric RELEASE"

registry = json.loads((APP / "data/venue-registry.json").read_text(encoding="utf-8"))
assert registry.get("policy", {}).get("canonical_data_source") == "app/data/venue-registry.json"
assert registry.get("venues"), "venue registry cannot be empty"
ids = [row.get("id") for row in registry["venues"]]
assert len(ids) == len(set(ids)), "duplicate canonical venue ids"
for row in registry["venues"]:
    assert row.get("id") and row.get("canonical_name")
    hours = row.get("opening_hours")
    if hours:
        assert hours.get("display"), f"{row['id']}: missing hours display"
        assert str(hours.get("source_url") or "").startswith("http"), f"{row['id']}: permanent hours need source_url"
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", str(hours.get("verified_at") or "")), f"{row['id']}: permanent hours need verified_at"

exhibition_hours = (APP / "exhibition-hours.js").read_text(encoding="utf-8")
schedule_display = (APP / "schedule-display.js").read_text(encoding="utf-8")
venue_hours = (APP / "venue-hours.mjs").read_text(encoding="utf-8")
gijon_hours = (APP / "gijon-venue-hours.js").read_text(encoding="utf-8")
assert "MHNV_HOURS" not in exhibition_hours
assert "venueHoursForDate" not in exhibition_hours, "retired exhibition-hours shim must not resolve venue hours"
assert "venueHoursForDate" in schedule_display, "schedule-display must own venue-hours presentation"
assert "nextVenueOpeningForDate" in schedule_display, "schedule-display must own next-opening presentation"
assert "exhibitionVisitHoursForDisplay" in schedule_display
assert "venueRecordForEvent" not in exhibition_hours and "venueRecordForName" not in exhibition_hours
assert "venueRecordForEvent" in venue_hours
assert "export function venueHoursForDate" in venue_hours
assert "style.textContent" not in exhibition_hours and 'createElement("style")' not in exhibition_hours
assert ".textContent =" not in exhibition_hours and "replaceChildren(" not in exhibition_hours
assert "GIJON_MUSEUM_DIRECTORY" not in gijon_hours
assert "const HOURS = new Map" not in gijon_hours
assert "venue-registry.generated.mjs" in gijon_hours
assert "venueRecordForEvent" in gijon_hours

app_js = (APP / "app.js").read_text(encoding="utf-8")
filter_safety = (APP / "combined-filters-safety.js").read_text(encoding="utf-8")
compact_css = (APP / "exhibition-compact.css").read_text(encoding="utf-8")
assert "multievent-layout-fix.js" not in app_js
assert "requestCanonicalFilterPass" in filter_safety
assert "static-exhibition-sentinels" not in filter_safety
assert re.search(r"\.hidden\s*=", filter_safety) is None, "filter safety must not own visibility"
assert "--agenda-group-row-min-height: 96px" in compact_css
assert "--agenda-group-list-max-height: 306px" in compact_css
for retired in (
    "exhibition-compact-loader.js",
    "exhibition-compact.js",
    "exhibition-gallery.js",
    "exhibition-venue-grouping.js",
    "multievent-layout-fix.js",
):
    assert not (APP / retired).exists(), f"retired runtime returned: {retired}"

service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
assert 'importScripts("./release-version.js", "./service-worker-assets.generated.js")' in service_worker
assert "const SHELL_ASSETS = [" not in service_worker
assert "__VIVAMOS_SHELL_ASSETS__" in service_worker

manifest_text = (APP / "service-worker-assets.generated.js").read_text(encoding="utf-8")
for token in (
    "./service-worker-assets.generated.js",
    "./venue-registry.generated.mjs",
    "./data/venue-registry.json",
    "./data/release-bundle.json",
    "./exhibition-groups.js",
):
    assert token in manifest_text, f"missing shell asset: {token}"
for retired in (
    "./exhibition-compact-loader.js",
    "./exhibition-compact.js",
    "./multievent-layout-fix.js",
):
    assert retired not in manifest_text, f"retired shell asset returned: {retired}"

generator = (APP / "scripts/generate_runtime_contracts.py").read_text(encoding="utf-8")
assert "assets = discover_runtime_assets()" in generator
assert "existing_assets() | discover_runtime_assets()" not in generator

bundle = json.loads((APP / "data/release-bundle.json").read_text(encoding="utf-8"))
assert bundle.get("release") == int(release_match.group(1))
assert str(bundle.get("release_id") or "").startswith(f"v{bundle['release']}-")
required_components = {
    "dataset_valparaiso",
    "dataset_gijon",
    "source_catalog",
    "source_registry",
    "diagnostic_source_coverage",
    "diagnostic_event_quality",
    "diagnostic_release_readiness",
    "venue_registry",
    "service_worker_manifest",
    "release_version",
}
assert required_components <= set((bundle.get("components") or {}).keys())

print("STRUCTURAL_HARDENING_OK")
