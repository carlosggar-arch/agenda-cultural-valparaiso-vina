from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

app_js = (APP / "app.js").read_text(encoding="utf-8")
index = (APP / "index.html").read_text(encoding="utf-8")
card_js = (APP / "card-experience.js").read_text(encoding="utf-8")
fallback_js = (APP / "card-image-fallback.js").read_text(encoding="utf-8")
service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
manifest = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))
gijon = json.loads((APP / "data/gijon/agenda_web.json").read_text(encoding="utf-8"))
valpo = json.loads((ROOT / "agenda_web.json").read_text(encoding="utf-8"))

# One installable shell, two independent datasets.
assert manifest["name"] == "¡Vivamos!"
assert manifest["start_url"] == "./"
assert manifest["scope"] == "./"
assert 'dataset: "../agenda_web.json"' in app_js
assert 'dataset: "./data/gijon/agenda_web.json"' in app_js
assert 'fetch(city.dataset' in app_js
assert 'new URL("../agenda_web.json", self.registration.scope).href' in service_worker
assert 'new URL("./data/gijon/agenda_web.json", self.registration.scope).href' in service_worker
assert 'v34 deliberately keeps both city datasets' in service_worker
assert 'await cache.put(request, response.clone())' in service_worker

# City can be chosen explicitly, remembered, or suggested from device location.
assert index.count('data-city-option="valparaiso"') == 1
assert index.count('data-city-option="gijon"') == 1
assert 'data-use-location' in index
assert 'new URLSearchParams(window.location.search).get("city")' in index
assert 'const STORAGE_KEY = "agenda-cultural-city"' in app_js
assert 'navigator.geolocation.getCurrentPosition' in app_js
assert 'function suggestCityFromCoordinates' in app_js

# Real event images keep precedence; placeholders become shared category photos.
assert 'event?.image?.url' in card_js
assert 'image.dataset.eventImage = "relevant"' in card_js
assert 'activeCity() !== "valparaiso"' not in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js
assert 'document.querySelectorAll(".event-card-media--placeholder")' in fallback_js

assert gijon.get("timezone") == "Europe/Madrid"
assert valpo.get("timezone") != "Europe/Madrid"
gijon_events = [event for event in gijon.get("events", []) if isinstance(event, dict)]
assert gijon_events, "Gijon dataset is unexpectedly empty"
assert any(
    str((event.get("image") or {}).get("url") or "").startswith(("http://", "https://"))
    for event in gijon_events
), "Gijon dataset must expose at least one official/relevant event image"
assert any(
    not str((event.get("image") or {}).get("url") or "").startswith(("http://", "https://"))
    for event in gijon_events
), "Gijon dataset should exercise the category fallback path"

print("PWA visual parity and multi-city dataset isolation: OK")
