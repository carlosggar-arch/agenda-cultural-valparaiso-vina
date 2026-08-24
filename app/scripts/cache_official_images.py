from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
REGISTRY_PATH = APP / "cities.json"
CACHE_ROOT = APP / "assets" / "event-images"
REPORT_PATH = APP / "data" / "quality" / "image-cache.json"
MAX_BYTES = 12 * 1024 * 1024
MIN_WIDTH = 240
MIN_HEIGHT = 160
MAX_EDGE = 1600


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def dataset_path(value: str) -> Path:
    return (APP / value).resolve()


def is_remote_image(value: object) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def safe_city_id(value: object) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", str(value or "city").casefold()).strip("-") or "city"


def download(url: str, timeout: int = 25) -> tuple[bytes, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; VivamosImageCache/1.0)",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    })
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - curated public image URLs
        content_type = response.headers.get_content_type()
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("image_too_large")
        return raw, content_type


def optimize(raw: bytes) -> tuple[bytes, int, int, str]:
    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.seek(0)
            image = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            width, height = image.size
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                raise ValueError("image_too_small")
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=84, method=6)
            return output.getvalue(), width, height, "webp"
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("invalid_image") from exc


def candidates(dataset: dict, today: date | None = None) -> list[dict]:
    today = today or datetime.now(ZoneInfo("UTC")).date()
    rows = []
    for event in dataset.get("events") or []:
        image = event.get("image") if isinstance(event.get("image"), dict) else {}
        origin = image.get("origin_url") or image.get("url")
        schedule = event.get("schedule") or {}
        raw_end = str(schedule.get("end") or schedule.get("start") or "")[:10]
        try:
            end_day = date.fromisoformat(raw_end) if raw_end else None
        except ValueError:
            end_day = None
        if is_remote_image(origin) and (end_day is None or end_day >= today):
            rows.append(event)
    return sorted(rows, key=lambda event: (
        str(((event.get("schedule") or {}).get("end") or (event.get("schedule") or {}).get("start") or "9999"))[:10],
        str(event.get("id") or ""),
    ))


def cache_dataset(dataset: dict, city_id: str, *, max_fetch: int, downloader=download, now: datetime | None = None, today: date | None = None) -> tuple[dict, list[dict], int]:
    rows: list[dict] = []
    fetched = 0
    verified_at = (now or datetime.now(ZoneInfo("UTC"))).isoformat(timespec="seconds")
    for event in candidates(dataset, today=today):
        image = event.setdefault("image", {})
        origin_url = str(image.get("origin_url") or image.get("url") or "").strip()
        cache = image.get("cache") if isinstance(image.get("cache"), dict) else {}
        cached_path = ROOT / str(cache.get("repository_path") or "")
        if cache.get("source_url") == origin_url and cached_path.is_file():
            rows.append({"id": event.get("id"), "state": "cached", "source_url": origin_url})
            continue
        if fetched >= max_fetch:
            rows.append({"id": event.get("id"), "state": "budget_exhausted", "source_url": origin_url})
            continue
        fetched += 1
        try:
            raw, content_type = downloader(origin_url)
            optimized, width, height, image_format = optimize(raw)
            digest = hashlib.sha256(optimized).hexdigest()
            repository_path = Path("app/assets/event-images") / safe_city_id(city_id) / f"{digest[:24]}.webp"
            destination = ROOT / repository_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                temporary = destination.with_suffix(".tmp")
                temporary.write_bytes(optimized)
                temporary.replace(destination)
            image["origin_url"] = origin_url
            image["url"] = f"./assets/event-images/{safe_city_id(city_id)}/{destination.name}"
            image["cache"] = {
                "source_url": origin_url,
                "repository_path": repository_path.as_posix(),
                "sha256": digest,
                "format": image_format,
                "width": width,
                "height": height,
                "cached_at": verified_at,
                "source_content_type": content_type,
            }
            rows.append({"id": event.get("id"), "state": "stored", "source_url": origin_url, "url": image["url"]})
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            rows.append({"id": event.get("id"), "state": "fetch_error", "source_url": origin_url, "error": f"{type(exc).__name__}: {exc}"})
    return dataset, rows, fetched


def build(max_fetch: int = 20, downloader=download) -> tuple[dict, dict[Path, dict]]:
    registry = load(REGISTRY_PATH)
    report_rows = []
    updated: dict[Path, dict] = {}
    total_fetched = 0
    for city in registry.get("cities") or []:
        city_id = str(city.get("id") or "").strip()
        path = dataset_path(str(city.get("dataset") or ""))
        timezone = str(city.get("timezone") or "UTC")
        dataset, rows, fetched = cache_dataset(
            load(path), city_id, max_fetch=max(0, max_fetch), downloader=downloader,
            today=datetime.now(ZoneInfo(timezone)).date(),
        )
        total_fetched += fetched
        updated[path] = dataset
        report_rows.append({"city": city_id, "dataset": path.relative_to(ROOT).as_posix(), "rows": rows})
    flat = [row for city in report_rows for row in city["rows"]]
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"),
        "fetch_budget_per_city": max_fetch,
        "fetched": total_fetched,
        "stored": sum(row["state"] == "stored" for row in flat),
        "fetch_errors": sum(row["state"] == "fetch_error" for row in flat),
        "cities": report_rows,
    }
    return report, updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache and optimize official event images for every registered city.")
    parser.add_argument("--max-fetch", type=int, default=20, help="Maximum downloads per registered city.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    report, updated = build(max_fetch=max(0, args.max_fetch))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_write:
        for path, dataset in updated.items():
            save(path, dataset)
        save(REPORT_PATH, report)


if __name__ == "__main__":
    main()
