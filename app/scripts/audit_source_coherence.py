from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from event_page_tools import fetch

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
COVERAGE_PATH = ROOT / "app/data/quality/source-coverage.json"
CATALOG_PATH = ROOT / "fuentes_publicas.json"
REPORT_PATH = ROOT / "app/data/quality/source-coherence.json"
CORE_POLICY_URL = "https://raw.githubusercontent.com/carlosggar-arch/agenda-cultural-core/main/config/valpo_high_value_zero_policy.json"
TIMEZONE = "America/Santiago"

ALIASES = {
    "insomnia teatro condell": "insomnia cine",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return ALIASES.get(value, value)


def parse_day(value: object) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def core_policy() -> tuple[str, dict]:
    ok, _, text, error = fetch(CORE_POLICY_URL)
    if not ok:
        return f"fetch_error:{error}", {}
    try:
        return "ok", json.loads(text)
    except json.JSONDecodeError:
        return "invalid_json", {}


def build(dataset: dict, coverage: dict, catalog: dict, today: date) -> dict:
    public_rows = catalog.get("sources") or []
    city = ((coverage.get("cities") or {}).get("valparaiso-vina") or {})
    coverage_rows = city.get("sources") or []
    public_names = [norm(row.get("name")) for row in public_rows if row.get("name")]
    coverage_names = [norm(row.get("name")) for row in coverage_rows if row.get("name")]
    public_name_set = set(public_names)
    coverage_name_set = set(coverage_names)

    duplicate_public_ids = sorted(
        sid for sid in {str(row.get("id") or "") for row in public_rows}
        if sid and sum(str(row.get("id") or "") == sid for row in public_rows) > 1
    )
    duplicate_public_names = sorted(name for name in set(public_names) if public_names.count(name) > 1)
    missing_in_coverage = sorted(
        str(row.get("name") or "") for row in public_rows if norm(row.get("name")) not in coverage_name_set
    )
    coverage_without_catalog = sorted(
        str(row.get("name") or "") for row in coverage_rows
        if norm(row.get("name")) not in public_name_set and not str(row.get("id") or "").startswith(("legacy_", "visitavina_", "portaltickets_", "valpocultura"))
    )

    stale = []
    for row in public_rows:
        verified = parse_day(row.get("last_verified_at"))
        if verified and (today - verified).days > 60:
            stale.append({"name": row.get("name"), "last_verified_at": row.get("last_verified_at"), "age_days": (today - verified).days})

    unattributed = [
        str(item.get("id") or "") for item in dataset.get("events") or []
        if not (item.get("source_id") or item.get("source_name"))
    ]

    core_state, policy = core_policy()
    core_missing = []
    for row in policy.get("sources") or []:
        candidates = [row.get("name")] + list(row.get("aliases") or [])
        if not any(norm(value) in public_name_set for value in candidates if value):
            core_missing.append(str(row.get("name") or row.get("id") or ""))

    critical = []
    if duplicate_public_ids:
        critical.append(f"duplicate_public_ids:{len(duplicate_public_ids)}")
    if duplicate_public_names:
        critical.append(f"duplicate_public_names:{len(duplicate_public_names)}")
    if unattributed:
        critical.append(f"unattributed_events:{len(unattributed)}")

    warnings = []
    if missing_in_coverage:
        warnings.append(f"public_sources_missing_in_coverage:{len(missing_in_coverage)}")
    if stale:
        warnings.append(f"stale_public_source_verifications:{len(stale)}")
    if core_state != "ok":
        warnings.append(f"core_policy:{core_state}")
    if core_missing:
        warnings.append(f"core_policy_without_public_source:{len(core_missing)}")

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
        "status": "critical" if critical else ("attention" if warnings else "healthy"),
        "critical": critical,
        "warnings": warnings,
        "summary": {
            "public_sources": len(public_rows),
            "coverage_sources": len(coverage_rows),
            "events": len(dataset.get("events") or []),
            "missing_in_coverage": len(missing_in_coverage),
            "coverage_without_catalog": len(coverage_without_catalog),
            "stale_verifications": len(stale),
            "core_policy_state": core_state,
            "core_policy_missing": len(core_missing),
        },
        "duplicate_public_ids": duplicate_public_ids,
        "duplicate_public_names": duplicate_public_names,
        "public_sources_missing_in_coverage": missing_in_coverage,
        "coverage_without_catalog": coverage_without_catalog,
        "stale_public_source_verifications": stale,
        "unattributed_event_ids": unattributed,
        "core_policy_without_public_source": core_missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit consistency among the public source catalog, source coverage, canonical dataset and core high-value policy.")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()
    report = build(load(DATASET_PATH), load(COVERAGE_PATH), load(CATALOG_PATH), datetime.now(ZoneInfo(TIMEZONE)).date())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_write:
        save(REPORT_PATH, report)
    if args.fail_on_critical and report["status"] == "critical":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
