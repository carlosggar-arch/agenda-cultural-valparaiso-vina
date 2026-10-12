from __future__ import annotations

import json
import base64
import hashlib
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import production_release_attestation as attestation

from production_pwa_smoke import CRITICAL_ASSETS, ORIGINS, release_number
from production_release_attestation import CITIES, STATES, build_attestation, validate_browser_log, write_markdown


OFFICIAL_IMAGE_EVENT_IDS = (
    "fixture-official-image-a",
    "fixture-official-image-b",
)
OFFICIAL_IMAGE_BYTES = (
    base64.b64decode('UklGRhwAAABXRUJQVlA4TA8AAAAvAAAAAAcQ/Y/+ByKi/wEA'),
    base64.b64decode('UklGRhwAAABXRUJQVlA4TA8AAAAvAAAAAAcQ0f/+ByKi/wEA'),
)
OFFICIAL_IMAGE_FILES = {
    event_id: hashlib.sha256(body).hexdigest()[:24] + '.webp'
    for event_id, body in zip(OFFICIAL_IMAGE_EVENT_IDS, OFFICIAL_IMAGE_BYTES)
}


@contextmanager
def committed_fixture_repository():
    """Exercise real immutable Git/image proof independently of live inventory."""
    with tempfile.TemporaryDirectory(prefix='attestation-fixture-repository-') as directory:
        root = Path(directory)
        for relative in {local for local, _remote in CRITICAL_ASSETS} | {'app/data/release-bundle.json'}:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(attestation.ROOT / relative, target)
        events = []
        for event_id, body in zip(OFFICIAL_IMAGE_EVENT_IDS, OFFICIAL_IMAGE_BYTES):
            path = 'app/assets/event-images/valparaiso/' + OFFICIAL_IMAGE_FILES[event_id]
            target = root / path; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            origin = 'https://official.example/' + OFFICIAL_IMAGE_FILES[event_id]
            events.append({'id': event_id, 'title': event_id, 'public_status': {'source_official': True},
                'image': {'url': './' + path.removeprefix('app/'), 'origin_url': origin,
                    'cache': {'source_url': origin, 'repository_path': path,
                        'sha256': hashlib.sha256(body).hexdigest(), 'width': 1, 'height': 1}}})
        (root / 'agenda_web.json').write_text(json.dumps({'events': events}), encoding='utf-8')
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c',
            'user.email=fixture@example.test', 'commit', '-qm', 'Immutable image evidence'], check=True)
        yield root


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def fixture_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for origin in ORIGINS:
        for city in CITIES:
            for state in STATES:
                ids = [f"{city}-{state}-a", f"{city}-{state}-b"]
                rows.append(
                    {
                        "origin": origin,
                        "city": city,
                        "state": state,
                        "at": "2026-08-23T22:46:00Z",
                        "count": len(ids),
                        "ids": ids,
                        "presentation": [
                            {"id": event_id, "category": "musica", "temporal": "today", "section": state}
                            for event_id in ids
                        ],
                    }
                )
    return rows


def expect_failure(fn, message: str) -> None:
    try:
        fn()
    except SystemExit:
        return
    raise AssertionError(message)


def main() -> None:
    release = release_number()
    with committed_fixture_repository() as repository, patch.object(attestation, 'ROOT', repository), \
            tempfile.TemporaryDirectory(prefix="vivamos-attestation-test-") as tmp:
        root = Path(tmp)
        http_log = root / "http.log"
        browser_log = root / "browser.log"
        warm_log = root / "warm.log"
        parity = root / "parity.json"
        markdown = root / "attestation.md"

        write(
            http_log,
            "\n".join(
                [
                    f"PRODUCTION_ORIGIN_PARITY_OK origin={origin} release=v{release} assets={len(CRITICAL_ASSETS)}\n"
                    f"PUBLISHED_PWA_SHELL_OK origin={origin} release=v{release}"
                    for origin in ORIGINS
                ]
            )
            + "\n",
        )
        write(
            browser_log,
            "\n".join(
                [
                    "PRODUCTION_COLD_LOAD_OK origin=github-pages city=valparaiso viewport=390x844 transport=selenium",
                    "PRODUCTION_COLD_LOAD_OK origin=github-pages city=gijon viewport=1280x900 transport=selenium",
                    "PRODUCTION_COLD_LOAD_OK origin=cloudflare city=valparaiso viewport=390x844 transport=selenium",
                    "PRODUCTION_COLD_LOAD_OK origin=cloudflare city=gijon viewport=1280x900 transport=selenium",
                    "PRODUCTION_CITY_ROUNDTRIP_OK origin=github-pages valparaiso->gijon->valparaiso filter=7-dias transport=selenium",
                ]
                + [
                    f"PRODUCTION_OFFICIAL_IMAGE_OK origin={origin} surface={surface} event={event_id} "
                    f"file={OFFICIAL_IMAGE_FILES[event_id]} natural=1x1"
                    for origin in ORIGINS
                    for surface in ("app", "web")
                    for event_id in OFFICIAL_IMAGE_EVENT_IDS
                ]
            )
            + "\n",
        )
        write(
            warm_log,
            "\n".join(
                [
                    f"PRODUCTION_WARM_REOPEN_OK origin=github-pages release=v{release} viewport=390x844 cold=1.66s warm=0.73s speedup=2.29x processed_cache=ready",
                    f"PRODUCTION_WARM_REOPEN_OK origin=cloudflare release=v{release} viewport=390x844 cold=1.62s warm=0.84s speedup=1.91x processed_cache=ready",
                ]
            )
            + "\n",
        )
        parity.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "mode": "production",
                    "at": "2026-08-23T22:46:00Z",
                    "rows": fixture_rows(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        payload = build_attestation(http_log, browser_log, warm_log, parity, verify_network=False)
        assert payload["release"] == release
        assert payload["critical_assets"]["count"] == len(CRITICAL_ASSETS)
        assert payload["critical_assets"]["network_reverified"] is False
        assert payload["publication_state"] == "published_and_visually_verified"
        assert set(payload["official_event_images"]) == set(OFFICIAL_IMAGE_EVENT_IDS)
        assert len(payload["web_pwa_exact_id_parity"]["rows"]) == len(ORIGINS) * len(CITIES) * len(STATES)
        write_markdown(markdown, payload)
        assert "Production release verification" in markdown.read_text(encoding="utf-8")

        browser_text = browser_log.read_text(encoding="utf-8")
        assert tuple(validate_browser_log(browser_text)) == OFFICIAL_IMAGE_EVENT_IDS
        # A fixture still proves committed dataset/bytes and exact file names;
        # local mutations cannot replace that immutable publication evidence.
        dataset = repository / 'agenda_web.json'
        original_dataset = dataset.read_bytes()
        dataset.write_text('{"events":[]}', encoding='utf-8')
        expect_failure(lambda: build_attestation(http_log, browser_log, warm_log, parity,
                       verify_network=False), 'uncommitted dataset changes must fail attestation')
        dataset.write_bytes(original_dataset)
        expect_failure(
            lambda: validate_browser_log(
                browser_text.replace(
                    "PRODUCTION_OFFICIAL_IMAGE_OK origin=cloudflare surface=web "
                    f"event={OFFICIAL_IMAGE_EVENT_IDS[1]}",
                    "MISSING_OFFICIAL_IMAGE",
                )
            ),
            "missing dynamic image evidence on one surface must fail attestation",
        )
        expect_failure(
            lambda: validate_browser_log(
                browser_text.replace(
                    "PRODUCTION_OFFICIAL_IMAGE_OK origin=cloudflare surface=web "
                    f"event={OFFICIAL_IMAGE_EVENT_IDS[1]}",
                    "PRODUCTION_OFFICIAL_IMAGE_OK origin=cloudflare surface=web event=agenda_other",
                )
            ),
            "mismatched dynamic image identity across origins must fail attestation",
        )
        expect_failure(
            lambda: validate_browser_log(
                browser_text.replace(
                    f"event={OFFICIAL_IMAGE_EVENT_IDS[1]} file={OFFICIAL_IMAGE_FILES[OFFICIAL_IMAGE_EVENT_IDS[1]]}",
                    f"event={OFFICIAL_IMAGE_EVENT_IDS[0]} file={OFFICIAL_IMAGE_FILES[OFFICIAL_IMAGE_EVENT_IDS[0]]}",
                )
            ),
            "repeated dynamic image identity must fail attestation",
        )

        broken = json.loads(parity.read_text(encoding="utf-8"))
        for row in broken["rows"]:
            if row["origin"] == "cloudflare" and row["city"] == "gijon" and row["state"] == "todos":
                row["ids"] = ["different"]
                row["count"] = 1
        parity.write_text(json.dumps(broken), encoding="utf-8")
        expect_failure(
            lambda: build_attestation(http_log, browser_log, warm_log, parity, verify_network=False),
            "cross-origin exact-ID mismatch must fail attestation",
        )

        parity.write_text(
            json.dumps({"schema_version": "1.0.0", "mode": "production", "at": "2026-08-23T22:46:00Z", "rows": fixture_rows()}),
            encoding="utf-8",
        )
        broken_presentation = json.loads(parity.read_text(encoding="utf-8"))
        for row in broken_presentation["rows"]:
            if row["origin"] == "cloudflare" and row["city"] == "valparaiso" and row["state"] == "hoy":
                row["presentation"][0]["category"] = "teatro"
        parity.write_text(json.dumps(broken_presentation), encoding="utf-8")
        expect_failure(
            lambda: build_attestation(http_log, browser_log, warm_log, parity, verify_network=False),
            "cross-origin category mismatch must fail attestation",
        )

        parity.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "mode": "production",
                    "at": "2026-08-23T22:46:00Z",
                    "rows": fixture_rows(),
                }
            ),
            encoding="utf-8",
        )
        original_http = http_log.read_text(encoding="utf-8")
        write(http_log, original_http.replace("PUBLISHED_PWA_SHELL_OK origin=cloudflare", "MISSING origin=cloudflare"))
        expect_failure(
            lambda: build_attestation(http_log, browser_log, warm_log, parity, verify_network=False),
            "missing production marker must fail attestation",
        )

    print("PRODUCTION_RELEASE_ATTESTATION_TESTS_OK")


if __name__ == "__main__":
    main()
