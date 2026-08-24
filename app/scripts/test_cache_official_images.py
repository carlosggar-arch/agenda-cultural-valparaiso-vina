from __future__ import annotations

import io
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image

import cache_official_images as cache

sys.path.insert(0, str(cache.ROOT / "scripts"))
import generate_event_pages  # noqa: E402


def fixture_image(width: int = 1920, height: int = 1280) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), (21, 91, 82)).save(output, format="PNG")
    return output.getvalue()


def test_multicity_cache_preserves_provenance_and_serves_local_copy() -> None:
    original_root = cache.ROOT
    original_cache = cache.CACHE_ROOT
    with tempfile.TemporaryDirectory() as directory:
        cache.ROOT = Path(directory)
        cache.CACHE_ROOT = Path(directory) / "app/assets/event-images"
        try:
            dataset = {"events": [{"id": "gijon_event_1", "title": "Evento oficial", "schedule": {"start": "2026-10-08T20:30:00+02:00"}, "image": {"url": "https://source.example/event.png", "alt": "Evento oficial"}}]}
            updated, rows, fetched = cache.cache_dataset(dataset, "gijon", max_fetch=1, downloader=lambda _url: (fixture_image(), "image/png"), now=datetime(2026, 8, 24, tzinfo=timezone.utc), today=date(2026, 8, 24))
            image = updated["events"][0]["image"]
            assert fetched == 1 and rows[0]["state"] == "stored"
            assert image["origin_url"] == "https://source.example/event.png"
            assert image["url"].startswith("./assets/event-images/gijon/")
            assert image["cache"]["source_url"] == image["origin_url"]
            assert (image["cache"]["width"], image["cache"]["height"]) == (1600, 1067)
            assert (Path(directory) / image["cache"]["repository_path"]).is_file()
        finally:
            cache.ROOT = original_root
            cache.CACHE_ROOT = original_cache


def test_source_failure_does_not_destroy_existing_local_copy() -> None:
    original_root = cache.ROOT
    original_cache = cache.CACHE_ROOT
    with tempfile.TemporaryDirectory() as directory:
        cache.ROOT = Path(directory)
        cache.CACHE_ROOT = Path(directory) / "app/assets/event-images"
        local = Path(directory) / "app/assets/event-images/gijon/existing.webp"
        local.parent.mkdir(parents=True)
        local.write_bytes(b"existing")
        dataset = {"events": [{"id": "gijon_event_2", "schedule": {"start": "2026-10-09"}, "image": {"url": "./assets/event-images/gijon/existing.webp", "origin_url": "https://source.example/unavailable.png", "cache": {"source_url": "https://source.example/unavailable.png", "repository_path": "app/assets/event-images/gijon/existing.webp"}}}]}
        try:
            updated, rows, fetched = cache.cache_dataset(dataset, "gijon", max_fetch=1, downloader=lambda _url: (_ for _ in ()).throw(OSError("offline")), today=date(2026, 8, 24))
            assert fetched == 0 and rows[0]["state"] == "cached"
            assert updated["events"][0]["image"]["url"] == "./assets/event-images/gijon/existing.webp"
        finally:
            cache.ROOT = original_root
            cache.CACHE_ROOT = original_cache


def test_static_event_pages_publish_owned_images_as_absolute_urls() -> None:
    assert generate_event_pages.public_image_url("./assets/event-images/gijon/event.webp") == (
        f"{generate_event_pages.SITE_BASE}/app/assets/event-images/gijon/event.webp"
    )


if __name__ == "__main__":
    test_multicity_cache_preserves_provenance_and_serves_local_copy()
    test_source_failure_does_not_destroy_existing_local_copy()
    test_static_event_pages_publish_owned_images_as_absolute_urls()
    print("Multicity official image cache: OK")
