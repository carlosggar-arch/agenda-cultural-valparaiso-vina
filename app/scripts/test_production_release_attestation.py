from __future__ import annotations

import json
import tempfile
from pathlib import Path

from production_pwa_smoke import CRITICAL_ASSETS, ORIGINS, release_number
from production_release_attestation import CITIES, OFFICIAL_IMAGE_EVENT_IDS, STATES, build_attestation, write_markdown


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
    with tempfile.TemporaryDirectory(prefix="vivamos-attestation-test-") as tmp:
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
                    f"PRODUCTION_OFFICIAL_IMAGE_OK origin={origin} surface={surface} event={event_id} file=fixture.webp natural=1600x1067"
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
