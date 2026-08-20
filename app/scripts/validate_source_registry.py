from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "app/data/source-registry.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get_path(payload: dict, dotted: str):
    value = payload
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def hostname(value: object) -> str:
    try:
        return urlparse(str(value or "")).hostname or ""
    except ValueError:
        return ""


def source_rows(dataset: dict) -> list[dict]:
    rows = dataset.get("sources") or []
    return rows if isinstance(rows, list) else []


def event_rows(dataset: dict) -> list[dict]:
    rows = dataset.get("events") or []
    return rows if isinstance(rows, list) else []


def validate(registry: dict, root: Path = ROOT) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if registry.get("schema_version") != "1.0.0": errors.append("registry_schema_version")

    public_path = root / str(registry.get("public_catalog") or "")
    coverage_path = root / str(registry.get("coverage_catalog") or "")
    if not public_path.is_file():
        return {"status": "error", "errors": [f"missing_public_catalog:{public_path}"], "warnings": warnings}
    if not coverage_path.is_file():
        return {"status": "error", "errors": [f"missing_coverage_catalog:{coverage_path}"], "warnings": warnings}

    public = load(public_path); coverage = load(coverage_path)
    public_rows = public.get("sources") or []
    aliases = registry.get("name_aliases") or {}; exceptions = registry.get("public_catalog_exceptions") or {}
    public_ids = [str(row.get("id") or "") for row in public_rows]
    public_names = [str(row.get("name") or "") for row in public_rows]
    if len(set(public_ids)) != len(public_ids): errors.append("duplicate_public_source_ids")
    if len(set(public_names)) != len(public_names): errors.append("duplicate_public_source_names")

    coverage_by_city = coverage.get("cities") or {}
    operational_ids: set[str] = set(); operational_names: set[str] = set()
    for city in coverage_by_city.values():
        for row in city.get("sources") or []:
            if row.get("id"): operational_ids.add(str(row["id"]))
            if row.get("name"): operational_names.add(str(row["name"]))

    missing_public_mappings = []
    for row in public_rows:
        name = str(row.get("name") or ""); alias = str(aliases.get(name) or "")
        if not (name in operational_names or alias in operational_ids or alias in operational_names) and name not in exceptions:
            missing_public_mappings.append(name)
    if missing_public_mappings:
        errors.append("public_sources_without_operational_mapping:" + ",".join(sorted(missing_public_mappings)))

    dataset_summaries = {}; verification_policies = registry.get("verification_policies") or {}
    for spec in registry.get("datasets") or []:
        dataset_id = str(spec.get("id") or ""); path = root / str(spec.get("path") or "")
        if not path.is_file():
            errors.append(f"missing_dataset:{dataset_id}:{path}"); continue
        dataset = load(path); sources = source_rows(dataset)
        source_ids = {str(row.get("id") or "") for row in sources if row.get("id")}
        coverage_city_id = str(spec.get("coverage_city_id") or "")
        if not source_ids and coverage_city_id:
            source_ids = {str(row.get("id") or "") for row in ((coverage_by_city.get(coverage_city_id) or {}).get("sources") or []) if row.get("id")}

        unattributed = []; unknown = []; verification_failures = []
        for event in event_rows(dataset):
            event_id = str(event.get("id") or "<unknown>"); source_id = str(event.get("source_id") or "")
            if not source_id:
                unattributed.append({"id": event_id, "title": str(event.get("title") or ""), "source_name": str(event.get("source_name") or "")})
                continue
            if source_id not in source_ids: unknown.append(f"{event_id}:{source_id}")
            policy = verification_policies.get(source_id) or {}
            if policy.get("policy") == "corroboration_required":
                blocked = {str(item).lower() for item in policy.get("blocked_public_hosts") or []}
                candidate = next((get_path(event, str(dotted)) for dotted in policy.get("candidate_paths") or [] if get_path(event, str(dotted)) and hostname(get_path(event, str(dotted))).lower() not in blocked), None)
                if not candidate: verification_failures.append(event_id)

        if unattributed: errors.append(f"{dataset_id}:events_without_source_id:{len(unattributed)}")
        if unknown: errors.append(f"{dataset_id}:events_with_unknown_source_id:{len(unknown)}")
        if verification_failures: errors.append(f"{dataset_id}:verification_policy_failures:{len(verification_failures)}")
        dataset_summaries[dataset_id] = {
            "events": len(event_rows(dataset)), "registered_sources": len(source_ids),
            "unattributed": len(unattributed), "unattributed_events": unattributed,
            "unknown_source_ids": len(unknown), "unknown_source_details": unknown,
            "verification_policy_failures": len(verification_failures), "verification_failure_ids": verification_failures,
        }

    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings,
            "missing_public_mappings": sorted(missing_public_mappings),
            "summary": {"public_sources": len(public_rows), "operational_sources": len(operational_ids), "datasets": dataset_summaries}}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the canonical source registry contract.")
    parser.add_argument("--registry", default=str(REGISTRY_PATH)); args = parser.parse_args()
    report = validate(load(Path(args.registry).resolve()), ROOT)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok": raise SystemExit(2)


if __name__ == "__main__": main()
