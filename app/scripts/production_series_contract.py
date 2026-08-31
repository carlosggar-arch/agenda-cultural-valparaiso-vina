from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, time, timezone
import hashlib
import json
import subprocess
import tempfile
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from production_pwa_smoke import ORIGINS, ROOT, release_number
from production_title_identity import IDENTITY_CONTRACT, evaluate_title_contract

CONTRACT_PATH = ROOT / "app/data/production-series-contracts.json"


@dataclass(frozen=True)
class DatasetSnapshot:
    origin: str
    path: str
    url: str
    body: bytes
    payload: dict[str, object]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


def load_contracts() -> list[dict[str, object]]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0.0":
        raise SystemExit("PRODUCTION_SERIES_CONTRACT_SCHEMA_INVALID")
    contracts = payload.get("contracts") or []
    if not contracts:
        raise SystemExit("PRODUCTION_SERIES_CONTRACTS_EMPTY")
    return [row for row in contracts if isinstance(row, dict)]


def snapshot_from_bytes(origin: str, path: str, url: str, body: bytes) -> DatasetSnapshot:
    try:
        payload = json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"PRODUCTION_SERIES_DATASET_INVALID origin={origin} path={path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise SystemExit(f"PRODUCTION_SERIES_DATASET_SHAPE_INVALID origin={origin} path={path}")
    return DatasetSnapshot(origin=origin, path=path, url=url, body=body, payload=payload)


def load_dataset_url(origin: str, base: str, dataset_path: str) -> DatasetSnapshot:
    url = urllib.parse.urljoin(base, dataset_path) + f"?series_contract={uuid.uuid4().hex}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "VivamosReleaseContract/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if response.status != 200 or "json" not in content_type:
                raise SystemExit(
                    f"PRODUCTION_SERIES_DATASET_INVALID origin={origin} path={dataset_path} status={response.status}"
                )
            body = response.read()
    except OSError as exc:
        raise SystemExit(f"PRODUCTION_SERIES_DATASET_UNAVAILABLE origin={origin} path={dataset_path}") from exc
    return snapshot_from_bytes(origin, dataset_path, url, body)


def local_dataset_snapshot(dataset_path: str) -> DatasetSnapshot:
    path = ROOT / "app" / dataset_path
    if not path.is_file():
        raise SystemExit(f"PRODUCTION_SERIES_LOCAL_DATASET_MISSING path={dataset_path}")
    repository_path = path.relative_to(ROOT).as_posix()
    try:
        body = subprocess.check_output(["git", "show", f"HEAD:{repository_path}"], cwd=ROOT)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"PRODUCTION_SERIES_CANONICAL_BLOB_MISSING path={repository_path}") from exc
    return snapshot_from_bytes("canonical-main", dataset_path, f"git:HEAD:{repository_path}", body)


def assert_dataset_identity(snapshots: list[DatasetSnapshot]) -> str:
    if not snapshots:
        raise SystemExit("PRODUCTION_SERIES_DATASET_SNAPSHOTS_EMPTY")
    paths = {snapshot.path for snapshot in snapshots}
    if len(paths) != 1:
        raise SystemExit(f"PRODUCTION_SERIES_DATASET_PATH_DIVERGENCE paths={sorted(paths)!r}")
    by_hash: dict[str, list[str]] = {}
    for snapshot in snapshots:
        by_hash.setdefault(snapshot.sha256, []).append(snapshot.origin)
    if len(by_hash) != 1:
        detail = ",".join(
            f"{digest}:{'+'.join(sorted(origins))}" for digest, origins in sorted(by_hash.items())
        )
        raise SystemExit(
            f"PRODUCTION_SERIES_DATASET_DIVERGENCE path={snapshots[0].path} hashes={detail}"
        )
    return snapshots[0].sha256


def rendered_titles(driver: object) -> list[str]:
    return driver.execute_script("return [...document.querySelectorAll('.event-card h4')].map((node) => String(node.textContent || '').trim()).filter(Boolean);")


def parse_schedule_instant(value: object, zone: ZoneInfo, *, end_of_day: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(text) == 10:
        parsed = datetime.combine(parsed.date(), time.max if end_of_day else time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


def event_occurrence_instants(event: dict[str, object], zone: ZoneInfo) -> list[datetime]:
    schedule = event.get("schedule") or {}
    if not isinstance(schedule, dict):
        return []
    instants = []
    for occurrence in schedule.get("occurrences") or []:
        if not isinstance(occurrence, dict):
            continue
        instant = parse_schedule_instant(occurrence.get("start"), zone)
        if instant:
            instants.append(instant)
    if instants:
        return instants
    start = parse_schedule_instant(schedule.get("start"), zone)
    end = parse_schedule_instant(schedule.get("end"), zone, end_of_day=True)
    return [instant for instant in (start, end) if instant]


def official_occurrence_instants(contract: dict[str, object], zone: ZoneInfo) -> list[datetime]:
    evidence = contract.get("official_evidence") or {}
    if not isinstance(evidence, dict) or not str(evidence.get("url") or "").startswith("https://"):
        raise SystemExit(f"PRODUCTION_SERIES_OFFICIAL_EVIDENCE_INVALID contract={contract.get('id')}")
    occurrences = evidence.get("occurrences") or []
    instants = [
        parse_schedule_instant(row.get("start"), zone)
        for row in occurrences
        if isinstance(row, dict)
    ]
    resolved = [instant for instant in instants if instant]
    if not resolved or len(resolved) != len(occurrences):
        raise SystemExit(f"PRODUCTION_SERIES_OFFICIAL_OCCURRENCES_INVALID contract={contract.get('id')}")
    return resolved


def scoped_events(dataset: dict[str, object], contract: dict[str, object]) -> list[dict[str, object]]:
    scope = contract.get("evidence_scope") or {}
    if not isinstance(scope, dict) or not scope:
        raise SystemExit("PRODUCTION_SERIES_EVIDENCE_SCOPE_MISSING")
    source_id = str(scope.get("source_id") or "")
    venue = str(scope.get("venue") or "")
    official_host = str(scope.get("official_host") or "")
    ticket_host = str(scope.get("ticket_host") or "")
    if not all((source_id, venue, official_host, ticket_host)):
        raise SystemExit("PRODUCTION_SERIES_EVIDENCE_SCOPE_INCOMPLETE")
    matches = []
    for event in dataset.get("events") or []:
        if not isinstance(event, dict) or event.get("source_id") != source_id:
            continue
        if str((event.get("location") or {}).get("venue") or "") != venue:
            continue
        links = event.get("links") or {}
        official = (urllib.parse.urlparse(str(links.get("official") or "")).hostname or "").removeprefix("www.")
        tickets = (urllib.parse.urlparse(str(links.get("tickets") or "")).hostname or "").removeprefix("www.")
        if official != official_host or tickets != ticket_host:
            continue
        matches.append(event)
    return matches


def contract_has_future_occurrences(
    dataset: dict[str, object], contract: dict[str, object], *, now: datetime | None = None
) -> tuple[bool, int, int, str]:
    if contract.get("lifecycle") != "active_occurrences":
        return True, 0, 0, "unbounded"
    zone_name = str(contract.get("timezone") or "")
    try:
        zone = ZoneInfo(zone_name)
    except Exception as exc:
        raise SystemExit(f"PRODUCTION_SERIES_TIMEZONE_INVALID timezone={zone_name}") from exc
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    official = official_occurrence_instants(contract, zone)
    expected_future = {instant for instant in official if instant >= reference}
    events = scoped_events(dataset, contract)
    actual = {instant for event in events for instant in event_occurrence_instants(event, zone)}
    actual_future = {instant for instant in actual if instant >= reference}
    missing_future = sorted(expected_future - actual)
    if missing_future:
        missing = ",".join(instant.isoformat() for instant in missing_future)
        raise SystemExit(
            f"PRODUCTION_SERIES_FUTURE_OCCURRENCE_MISSING contract={contract.get('id')} occurrences={missing}"
        )
    active = bool(expected_future or actual_future)
    latest = max(set(official) | actual).isoformat()
    return active, len(events), len(actual_future), latest


def verify_contract(origin: str, base: str, contract: dict[str, object], expected_release: int, dataset: dict[str, object]) -> None:
    from selenium import webdriver
    from selenium.webdriver.support.ui import WebDriverWait

    from production_browser_selenium_smoke import READY_TIMEOUT_SECONDS, chrome_options, runtime_ready

    city = str(contract.get("city") or "")
    section = str(contract.get("section") or "todos")
    contract_id = str(contract.get("id") or "unnamed")
    active, evidence_events, future_occurrences, latest = contract_has_future_occurrences(dataset, contract)
    if not active:
        print(
            f"PRODUCTION_SERIES_CONTRACT_EXPIRED origin={origin} contract={contract_id} "
            f"evidence_events={evidence_events} future_occurrences=0 latest={latest}"
        )
        return
    with tempfile.TemporaryDirectory(prefix=f"vivamos-series-{origin}-{city}-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 1280, 900))
        try:
            driver.get(f"{base}?city={city}&when={section}&series_contract={uuid.uuid4().hex}")
            WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(lambda current: runtime_ready(current, city, expected_release))
            titles = rendered_titles(driver)
        finally:
            driver.quit()

    result = evaluate_title_contract(
        titles,
        expected_titles=contract.get("expected_titles") or [],
        preserved_titles=contract.get("preserved_titles") or [],
        forbidden_titles=contract.get("forbidden_exact_titles") or [],
    )
    failures = {key: values for key, values in result.items() if values}
    if failures:
        raise SystemExit(
            f"PRODUCTION_SERIES_CONTRACT_FAILED origin={origin} contract={contract_id} "
            f"title_identity={IDENTITY_CONTRACT} failures={failures}"
        )
    print(
        f"PRODUCTION_SERIES_CONTRACT_OK origin={origin} contract={contract_id} city={city} section={section} "
        f"expected={len(contract.get('expected_titles') or [])} preserved={len(contract.get('preserved_titles') or [])} "
        f"future_occurrences={future_occurrences} title_identity={IDENTITY_CONTRACT} cardinality=one-to-one"
    )


def main() -> None:
    argparse.ArgumentParser(description="Verify data-driven event-series publication contracts on every production origin.").parse_args()
    expected_release = release_number()
    contracts = load_contracts()
    snapshots_by_path: dict[str, dict[str, DatasetSnapshot]] = {}
    for contract in contracts:
        dataset_path = str(contract.get("dataset_path") or "")
        if not dataset_path:
            raise SystemExit(f"PRODUCTION_SERIES_DATASET_PATH_MISSING contract={contract.get('id')}")
        snapshots_by_path.setdefault(dataset_path, {})["canonical-main"] = local_dataset_snapshot(dataset_path)
    for dataset_path, snapshots in snapshots_by_path.items():
        for origin, base in ORIGINS.items():
            snapshots[origin] = load_dataset_url(origin, base, dataset_path)
        identity_hash = assert_dataset_identity(list(snapshots.values()))
        print(
            f"PRODUCTION_SERIES_DATASET_IDENTITY_OK path={dataset_path} sha256={identity_hash} "
            f"origins={','.join(sorted(snapshots))}"
        )
    for origin, base in ORIGINS.items():
        for contract in contracts:
            dataset_path = str(contract.get("dataset_path") or "")
            verify_contract(origin, base, contract, expected_release, snapshots_by_path[dataset_path][origin].payload)
    print(f"PRODUCTION_SERIES_CONTRACTS_VERIFIED contracts={len(contracts)} origins={len(ORIGINS)} title_identity={IDENTITY_CONTRACT}")


if __name__ == "__main__":
    main()
