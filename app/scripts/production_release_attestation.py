from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from production_pwa_smoke import CRITICAL_ASSETS, ORIGINS, ROOT, fetch_bytes, release_number

SCHEMA_VERSION = "1.0.0"
CITIES = ("valparaiso", "gijon")
STATES = ("hoy", "7-dias", "todos")
OFFICIAL_IMAGE_EVENT_IDS = (
    "agenda_baburizza_82ca6a27bc5861af85cb",
    "agenda_baburizza_a37f94515515258cdea3",
)


def read_text(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Missing production evidence file: {path}")
    return path.read_text(encoding="utf-8")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def release_bundle() -> dict:
    payload = json.loads((ROOT / "app/data/release-bundle.json").read_text(encoding="utf-8"))
    expected = release_number()
    if int(payload.get("release") or -1) != expected:
        raise SystemExit(f"Release bundle mismatch: bundle={payload.get('release')} runtime={expected}")
    return payload


def require_marker(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise SystemExit(f"Missing {label} evidence marker: {marker}")


def parse_warm_metrics(text: str, release: int) -> dict[str, dict[str, object]]:
    pattern = re.compile(
        r"PRODUCTION_WARM_REOPEN_OK origin=(?P<origin>\S+) release=v(?P<release>\d+) "
        r"viewport=(?P<viewport>\S+) cold=(?P<cold>[0-9.]+)s warm=(?P<warm>[0-9.]+)s "
        r"speedup=(?P<speedup>[0-9.]+)x processed_cache=ready"
    )
    rows: dict[str, dict[str, object]] = {}
    for match in pattern.finditer(text):
        origin = match.group("origin")
        rows[origin] = {
            "release": int(match.group("release")),
            "viewport": match.group("viewport"),
            "cold_seconds": float(match.group("cold")),
            "warm_seconds": float(match.group("warm")),
            "speedup": float(match.group("speedup")),
            "processed_cache": "ready",
        }
    for origin in ORIGINS:
        row = rows.get(origin)
        if not row:
            raise SystemExit(f"Missing warm-reopen evidence for {origin}")
        if row["release"] != release:
            raise SystemExit(f"Warm-reopen release mismatch for {origin}: {row['release']} != {release}")
    return rows


def validate_http_log(text: str, release: int) -> None:
    for origin in ORIGINS:
        require_marker(
            text,
            f"PRODUCTION_ORIGIN_PARITY_OK origin={origin} release=v{release} assets={len(CRITICAL_ASSETS)}",
            "origin byte-parity",
        )
        require_marker(text, f"PUBLISHED_PWA_SHELL_OK origin={origin} release=v{release}", "published shell")


def validate_browser_log(text: str) -> None:
    viewports = {"valparaiso": "390x844", "gijon": "1280x900"}
    for origin in ORIGINS:
        for city in CITIES:
            require_marker(
                text,
                f"PRODUCTION_COLD_LOAD_OK origin={origin} city={city} viewport={viewports[city]} transport=selenium",
                "cold-load",
            )
    require_marker(
        text,
        "PRODUCTION_CITY_ROUNDTRIP_OK origin=github-pages valparaiso->gijon->valparaiso filter=7-dias transport=selenium",
        "city roundtrip",
    )
    for origin in ORIGINS:
        for surface in ("app", "web"):
            for event_id in OFFICIAL_IMAGE_EVENT_IDS:
                require_marker(
                    text,
                    f"PRODUCTION_OFFICIAL_IMAGE_OK origin={origin} surface={surface} event={event_id}",
                    "rendered official image",
                )


def validate_parity_report(path: Path) -> tuple[str, list[dict[str, object]]]:
    payload = json.loads(read_text(path))
    if payload.get("schema_version") != "1.0.0" or payload.get("mode") != "production":
        raise SystemExit("Unexpected WEB/PWA parity evidence schema or mode")
    rows = payload.get("rows") or []
    expected = {(origin, city, state) for origin in ORIGINS for city in CITIES for state in STATES}
    indexed: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row.get("origin")), str(row.get("city")), str(row.get("state")))
        if key in indexed:
            raise SystemExit(f"Duplicate WEB/PWA parity row: {key}")
        ids = row.get("ids") or []
        if int(row.get("count") or -1) != len(ids) or len(ids) != len(set(ids)):
            raise SystemExit(f"Invalid exact-ID evidence row: {key}")
        presentation = row.get("presentation") or []
        if len(presentation) != len(ids) or [item.get("id") for item in presentation] != ids:
            raise SystemExit(f"Invalid ordered presentation evidence row: {key}")
        if any(
            item.get("section") != key[2] or not item.get("category") or not item.get("temporal")
            for item in presentation
        ):
            raise SystemExit(f"Incomplete category/section/temporal evidence row: {key}")
        indexed[key] = row
    if set(indexed) != expected:
        missing = sorted(expected - set(indexed))
        extra = sorted(set(indexed) - expected)
        raise SystemExit(f"Incomplete WEB/PWA parity evidence: missing={missing} extra={extra}")
    for city in CITIES:
        for state in STATES:
            gh = indexed[("github-pages", city, state)]["ids"]
            cf = indexed[("cloudflare", city, state)]["ids"]
            if gh != cf:
                raise SystemExit(f"Cross-origin exact-ID mismatch after WEB/PWA parity: city={city} state={state}")
            gh_presentation = indexed[("github-pages", city, state)]["presentation"]
            cf_presentation = indexed[("cloudflare", city, state)]["presentation"]
            if gh_presentation != cf_presentation:
                raise SystemExit(f"Cross-origin presentation mismatch after WEB/PWA parity: city={city} state={state}")
    return str(payload.get("at") or ""), [indexed[key] for key in sorted(indexed)]


def remote_hash_attestation() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    local_hashes: dict[str, str] = {}
    for local, _remote in CRITICAL_ASSETS:
        local_hashes[local] = hashlib.sha256((ROOT / local).read_bytes()).hexdigest()

    origins: dict[str, dict[str, str]] = {}
    for origin, base in ORIGINS.items():
        hashes: dict[str, str] = {}
        for local, remote in CRITICAL_ASSETS:
            actual = hashlib.sha256(fetch_bytes(base, remote)).hexdigest()
            expected = local_hashes[local]
            if actual != expected:
                raise SystemExit(
                    f"Final attestation byte mismatch origin={origin} asset={local} actual={actual} expected={expected}"
                )
            hashes[local] = actual
        origins[origin] = hashes
    return local_hashes, origins


def official_image_attestation(*, verify_network: bool) -> dict[str, dict[str, object]]:
    payload = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))
    indexed = {str(event.get("id") or ""): event for event in payload.get("events") or []}
    evidence: dict[str, dict[str, object]] = {}
    for event_id in OFFICIAL_IMAGE_EVENT_IDS:
        event = indexed.get(event_id)
        if not event:
            raise SystemExit(f"Official image fixture disappeared from dataset: {event_id}")
        image = event.get("image") or {}
        relative = str(image.get("url") or "")
        origin_url = str(image.get("origin_url") or "")
        cache = image.get("cache") or {}
        source_url = str(cache.get("source_url") or "")
        repository_path = str(cache.get("repository_path") or "")
        if not relative.startswith("./assets/event-images/valparaiso/"):
            raise SystemExit(f"Official image fixture is not repository-owned: {event_id} {relative}")
        if not origin_url.startswith("http") or source_url != origin_url:
            raise SystemExit(f"Official image provenance is incomplete: {event_id}")
        expected_repository_path = f"app/{relative.removeprefix('./')}"
        if repository_path != expected_repository_path:
            raise SystemExit(
                f"Official image repository path mismatch: {event_id} {repository_path} != {expected_repository_path}"
            )
        local = ROOT / repository_path
        local_sha = hashlib.sha256(local.read_bytes()).hexdigest()
        origin_hashes: dict[str, str] = {}
        if verify_network:
            for origin, base in ORIGINS.items():
                remote = f"{base}{relative.removeprefix('./')}"
                actual = hashlib.sha256(fetch_bytes(remote, "")).hexdigest()
                if actual != local_sha:
                    raise SystemExit(
                        f"Official image byte mismatch origin={origin} event={event_id} actual={actual} expected={local_sha}"
                    )
                origin_hashes[origin] = actual
        evidence[event_id] = {
            "title": event.get("title"),
            "published_url": relative,
            "origin_url": origin_url,
            "repository_path": repository_path,
            "sha256": local_sha,
            "dimensions": [cache.get("width"), cache.get("height")],
            "origins_sha256": origin_hashes,
            "visually_verified_surfaces": ["app", "web"],
        }
    return evidence


def build_attestation(
    http_log: Path,
    browser_log: Path,
    warm_log: Path,
    parity_report: Path,
    *,
    verify_network: bool = True,
) -> dict[str, object]:
    release = release_number()
    bundle = release_bundle()
    http_text = read_text(http_log)
    browser_text = read_text(browser_log)
    warm_text = read_text(warm_log)

    validate_http_log(http_text, release)
    validate_browser_log(browser_text)
    warm = parse_warm_metrics(warm_text, release)
    parity_at, parity_rows = validate_parity_report(parity_report)

    if verify_network:
        local_hashes, origin_hashes = remote_hash_attestation()
    else:
        local_hashes = {
            local: hashlib.sha256((ROOT / local).read_bytes()).hexdigest()
            for local, _remote in CRITICAL_ASSETS
        }
        origin_hashes = {}
    official_images = official_image_attestation(verify_network=verify_network)

    head = git_head()
    return {
        "schema_version": SCHEMA_VERSION,
        "verified_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "head_sha": head,
        "release": release,
        "release_id": bundle.get("release_id"),
        "release_fingerprint": bundle.get("fingerprint"),
        "workflow": {
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "workflow": os.getenv("GITHUB_WORKFLOW"),
        },
        "critical_assets": {
            "count": len(CRITICAL_ASSETS),
            "local_sha256": local_hashes,
            "origins_sha256": origin_hashes,
            "network_reverified": verify_network,
        },
        "official_event_images": official_images,
        "cold_load": {
            "origins": list(ORIGINS),
            "cities": list(CITIES),
            "roundtrip": "valparaiso->gijon->valparaiso",
            "roundtrip_filter": "7-dias",
        },
        "warm_reopen": warm,
        "web_pwa_exact_id_parity": {
            "at": parity_at,
            "rows": parity_rows,
        },
        "publication_state": "published_and_visually_verified",
    }


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    parity = payload["web_pwa_exact_id_parity"]
    rows = parity["rows"]
    lines = [
        "## Production release verification",
        "",
        f"- Head: `{payload['head_sha']}`",
        f"- Release: `v{payload['release']}` (`{payload['release_id']}`)",
        f"- Critical assets: {payload['critical_assets']['count']} byte-identical on GitHub Pages and Cloudflare",
        "- Cold load: Valparaíso + Gijón on both origins; city roundtrip OK",
        "- Warm PWA reopen: GitHub Pages + Cloudflare OK",
        f"- Exact WEB↔cached/offline PWA parity: {len(rows)} origin/city/state rows",
        f"- Official event images: {len(payload['official_event_images'])} byte-identical and visibly rendered on WEB + App",
        "- Publication state: `published_and_visually_verified`",
        "",
        "| Origin | City | State | IDs |",
        "| --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(f"| {row['origin']} | {row['city']} | {row['state']} | {row['count']} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an auditable attestation only after the complete production sequence succeeds.")
    parser.add_argument("--http-log", required=True)
    parser.add_argument("--browser-log", required=True)
    parser.add_argument("--warm-log", required=True)
    parser.add_argument("--parity-report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output", default=None)
    parser.add_argument("--no-network", action="store_true", help="Unit-test only: validate evidence without refetching production assets.")
    args = parser.parse_args()

    payload = build_attestation(
        Path(args.http_log),
        Path(args.browser_log),
        Path(args.warm_log),
        Path(args.parity_report),
        verify_network=not args.no_network,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output:
        write_markdown(Path(args.markdown_output), payload)

    if args.no_network:
        print(f"PRODUCTION_RELEASE_ATTESTATION_TEST_OK release=v{payload['release']} rows={len(payload['web_pwa_exact_id_parity']['rows'])}")
    else:
        print(
            "PRODUCTION_RELEASE_VERIFIED "
            f"head={payload['head_sha']} release=v{payload['release']} release_id={payload['release_id']} "
            f"assets={payload['critical_assets']['count']} official_images={len(payload['official_event_images'])} "
            f"parity_rows={len(payload['web_pwa_exact_id_parity']['rows'])} state={payload['publication_state']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
