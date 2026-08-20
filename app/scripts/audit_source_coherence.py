from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "agenda_web.json"
COVERAGE_PATH = ROOT / "app/data/quality/source-coverage.json"
CATALOG_PATH = ROOT / "fuentes_publicas.json"
REGISTRY_PATH = ROOT / "app/data/source-registry.json"
REPORT_PATH = ROOT / "app/data/quality/source-coherence.json"
TIMEZONE = "America/Santiago"

ALIASES = {
    "insomnia teatro condell": "insomnia cine",
}

REQUIRED_REGISTRY_FLAGS = (
    "event_source_id_required",
    "event_source_must_be_registered",
    "new_public_source_requires_operational_mapping",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return ALIASES.get(value, value)


def source_id(value: object) -> str:
    return str(value or "").strip()


def parse_day(value: object) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return None


def core_policy() -> tuple[str, dict]:
    """Compatibility shim for older tests/callers; source coherence is now local-registry based."""
    return "retired_local_registry", {}


def default_registry() -> dict:
    return {
        "requirements": {flag: True for flag in REQUIRED_REGISTRY_FLAGS},
        "name_aliases": {},
        "public_catalog_exceptions": {},
    }


def build(dataset: dict, coverage: dict, catalog: dict, today: date, registry: dict | None = None) -> dict:
    registry = registry or default_registry()
    public_rows = catalog.get("sources") or []
    city = ((coverage.get("cities") or {}).get("valparaiso-vina") or {})
    coverage_rows = city.get("sources") or []

    public_names = [norm(row.get("name")) for row in public_rows if row.get("name")]
    coverage_names = [norm(row.get("name")) for row in coverage_rows if row.get("name")]
    public_name_set = set(public_names)
    coverage_name_set = set(coverage_names)
    coverage_ids = {source_id(row.get("id")) for row in coverage_rows if source_id(row.get("id"))}

    registry_aliases = {
        norm(name): source_id(target)
        for name, target in (registry.get("name_aliases") or {}).items()
        if norm(name) and source_id(target)
    }
    registry_exceptions = {
        norm(name): str(reason or "").strip()
        for name, reason in (registry.get("public_catalog_exceptions") or {}).items()
        if norm(name)
    }

    duplicate_public_ids = sorted(
        sid for sid in {source_id(row.get("id")) for row in public_rows}
        if sid and sum(source_id(row.get("id")) == sid for row in public_rows) > 1
    )
    duplicate_public_names = sorted(name for name in set(public_names) if public_names.count(name) > 1)

    missing_in_coverage: list[str] = []
    operational_aliases: list[dict] = []
    explicit_exceptions: list[dict] = []
    public_operational_ids: set[str] = set()

    for row in public_rows:
        name = str(row.get("name") or "").strip()
        name_key = norm(name)
        canonical_id = source_id(row.get("canonical_source_id"))
        alias_id = registry_aliases.get(name_key, "")
        if canonical_id:
            public_operational_ids.add(canonical_id)
        if alias_id:
            public_operational_ids.add(alias_id)

        if name_key in coverage_name_set:
            continue
        if canonical_id and canonical_id in coverage_ids:
            continue
        if alias_id and alias_id in coverage_ids:
            operational_aliases.append({"name": name, "coverage_source_id": alias_id})
            continue
        if name_key in registry_exceptions:
            explicit_exceptions.append({"name": name, "reason": registry_exceptions[name_key]})
            continue
        missing_in_coverage.append(name)

    coverage_without_catalog = sorted(
        str(row.get("name") or "")
        for row in coverage_rows
        if norm(row.get("name")) not in public_name_set
        and source_id(row.get("id")) not in public_operational_ids
        and not source_id(row.get("id")).startswith(("legacy_", "visitavina_", "portaltickets_", "valpocultura"))
    )

    stale = []
    for row in public_rows:
        verified = parse_day(row.get("last_verified_at"))
        if verified and (today - verified).days > 60:
            stale.append({"name": row.get("name"), "last_verified_at": row.get("last_verified_at"), "age_days": (today - verified).days})

    unattributed = [
        source_id(item.get("id")) for item in dataset.get("events") or []
        if not source_id(item.get("source_id"))
    ]

    requirements = registry.get("requirements") or {}
    registry_contract_errors = [flag for flag in REQUIRED_REGISTRY_FLAGS if requirements.get(flag) is not True]

    critical = []
    if duplicate_public_ids:
        critical.append(f"duplicate_public_ids:{len(duplicate_public_ids)}")
    if duplicate_public_names:
        critical.append(f"duplicate_public_names:{len(duplicate_public_names)}")
    if unattributed:
        critical.append(f"unattributed_events:{len(unattributed)}")
    if registry_contract_errors:
        critical.append(f"registry_contract_errors:{len(registry_contract_errors)}")

    warnings = []
    if missing_in_coverage:
        warnings.append(f"public_sources_missing_in_coverage:{len(missing_in_coverage)}")
    if stale:
        warnings.append(f"stale_public_source_verifications:{len(stale)}")

    return {
        "schema_version": "2.0.0",
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
            "operational_aliases": len(operational_aliases),
            "explicit_catalog_exceptions": len(explicit_exceptions),
            "stale_verifications": len(stale),
            "registry_state": "ok" if not registry_contract_errors else "invalid_contract",
        },
        "duplicate_public_ids": duplicate_public_ids,
        "duplicate_public_names": duplicate_public_names,
        "public_sources_missing_in_coverage": sorted(missing_in_coverage),
        "public_sources_with_operational_alias": sorted(operational_aliases, key=lambda row: row["name"]),
        "public_catalog_exceptions_applied": sorted(explicit_exceptions, key=lambda row: row["name"]),
        "coverage_without_catalog": coverage_without_catalog,
        "stale_public_source_verifications": stale,
        "unattributed_event_ids": unattributed,
        "registry_contract_errors": registry_contract_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit consistency among the public source catalog, source coverage, canonical datasets and local source registry."
    )
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()
    report = build(
        load(DATASET_PATH),
        load(COVERAGE_PATH),
        load(CATALOG_PATH),
        datetime.now(ZoneInfo(TIMEZONE)).date(),
        registry=load(REGISTRY_PATH),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_write:
        save(REPORT_PATH, report)
    if args.fail_on_critical and report["status"] == "critical":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
