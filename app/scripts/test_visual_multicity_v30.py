from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

app_js = (APP / "app.js").read_text(encoding="utf-8")
app_js += "\n" + (APP / "app-core.js").read_text(encoding="utf-8")
index = (APP / "index.html").read_text(encoding="utf-8")
card_js = (APP / "card-experience.js").read_text(encoding="utf-8")
fallback_js = (APP / "card-image-fallback.js").read_text(encoding="utf-8")
service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
media_layout = (ROOT / "assets" / "event-media-layout.css").read_text(encoding="utf-8")
manifest = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))
registry = json.loads((APP / "cities.json").read_text(encoding="utf-8"))
gijon = json.loads((APP / "data/gijon/agenda_web.json").read_text(encoding="utf-8"))
valpo = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))

cities = {city["id"]: city for city in registry["cities"]}
assert registry["default_city"] in cities
assert {"valparaiso", "gijon"}.issubset(cities)
assert len(cities) >= 2

# One installable shell, registry-driven independent datasets.
assert manifest["name"] == "¡Vivamos!"
assert manifest["start_url"] == "./"
assert manifest["scope"] == "./"
assert 'loadCityRegistry' in app_js
assert 'const CITIES = CITY_REGISTRY.byId' in app_js
assert 'fetch(city.dataset' in app_js
assert '"./cities.json"' in service_worker
assert 'async function datasetUrls()' in service_worker
assert 'new URL(city.dataset, self.registration.scope).href' in service_worker
assert 'async function warmDatasetCache()' in service_worker

# City choices are generated from the registry, remembered, or suggested from device location.
assert 'data-city-options' in index
assert index.count('data-city-option="valparaiso"') == 0
assert index.count('data-city-option="gijon"') == 0
assert 'data-use-location' in index
assert 'new URLSearchParams(window.location.search).get("city")' in index
assert 'CITY_STORAGE_KEY' in app_js
assert 'navigator.geolocation.getCurrentPosition' in app_js
assert 'function suggestCityFromCoordinates' in app_js

# Real event images keep precedence; card placeholders can still become shared category photos.
assert 'event?.image?.url' in card_js
assert 'image.dataset.eventImage = representative ? "representative" : "relevant"' in card_js
assert 'activeCity() !== "valparaiso"' not in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js

# WEB + APP media must remain presentation-only. Generic source illustrations are
# cropped enough to hide baked-in white carousel strips/arrows; real event photos
# keep their contain treatment and are not subjected to this crop.
for selector in (
    '.card-media > button',
    '.event-card-media > button',
    '.event-detail-media > button',
    '.card-media .carousel-control-next',
    '.card-media .carousel-control-prev',
    '.card-media .swiper-button-next',
    '.card-media .swiper-button-prev',
    '.card-media [data-media-nav]',
):
    assert selector in media_layout
assert 'display: none !important;' in media_layout
assert 'img[data-image-kind="category-fallback"]' in media_layout
assert 'img[src*="categoria-"]' in media_layout
assert 'object-fit: cover !important;' in media_layout
assert 'transform: scale(1.25) !important;' in media_layout
assert 'object-fit: contain !important;' in media_layout

assert gijon.get("timezone") == cities["gijon"]["timezone"]
assert valpo.get("timezone") != cities["gijon"]["timezone"]
gijon_events = [event for event in gijon.get("events", []) if isinstance(event, dict)]
assert gijon_events, "Gijon dataset is unexpectedly empty"
assert any(str((event.get("image") or {}).get("url") or "").startswith(("http://", "https://")) for event in gijon_events)

print("PWA registry-driven multi-city dataset isolation and WEB/APP media cleanup: OK")