from __future__ import annotations

import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
ASSETS = ROOT / "assets"

registry = json.loads((APP / "cities.json").read_text(encoding="utf-8"))
assert registry.get("schema_version") == "1.0.0"
assert isinstance(registry.get("cities"), list) and len(registry["cities"]) >= 2
ids = [str(city.get("id") or "") for city in registry["cities"]]
assert len(ids) == len(set(ids))
assert registry.get("default_city") in ids

required = {"id", "label", "timezone", "locale", "lang", "dataset", "theme_color", "center", "radius_km", "areas"}
for city in registry["cities"]:
    assert required.issubset(city), f"Incomplete city descriptor: {city.get('id')}"
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", city["id"])
    assert isinstance(city["center"].get("lat"), (int, float))
    assert isinstance(city["center"].get("lon"), (int, float))
    assert isinstance(city["radius_km"], (int, float)) and city["radius_km"] > 0

# A synthetic third descriptor must fit the same contract without changing runtime code.
third = copy.deepcopy(registry["cities"][1])
third.update({
    "id": "tercera-ciudad-test",
    "label": "Tercera ciudad de prueba",
    "subtitle": "Tercera ciudad de prueba",
    "dataset": "./data/tercera-ciudad-test/agenda_web.json",
    "theme_color": "#345678",
    "center": {"lat": 0.0, "lon": 0.0},
    "radius_km": 35,
    "areas": [],
})
assert required.issubset(third)
assert third["id"] not in ids

# Registry consumption may be direct or through the app-core entrypoint. Keep the
# contract architectural rather than requiring an unused import in app.js.
app_entry = (APP / "app.js").read_text(encoding="utf-8")
app_core = (APP / "app-core.js").read_text(encoding="utf-8")
assert "app-core.js" in app_entry, "app.js must load app-core.js"
assert "city-registry.mjs" in app_core, "app-core.js does not consume the canonical city registry"

runtime_files = {
    "first_run": (APP / "city-first-run.js").read_text(encoding="utf-8"),
    "filters": (APP / "combined-filters.js").read_text(encoding="utf-8"),
    "favorites": (APP / "favorites.js").read_text(encoding="utf-8"),
    "planning": (APP / "plan-ahead.js").read_text(encoding="utf-8"),
    "mis_planes": (APP / "mis-planes.html").read_text(encoding="utf-8"),
}
for name, text in runtime_files.items():
    assert "city-registry.mjs" in text, f"{name} does not consume the canonical city registry"

# Presentation invariant: a third city must inherit the same renderer. Local
# differences are permitted only as data/configuration/adapter behavior.
common_presentation = [
    "temporal-priority.js",
    "exhibition-groups.js",
    "schedule-display.js",
    "exhibition-hours.js",
    "card-experience.js",
    "public-presentation-guard.js",
    "image-quality-guard.js",
]
for module in common_presentation:
    assert module in app_entry, f"{module} is not loaded by the shared presentation runtime"

for forbidden in ["GIJON_DEFERRED_MODULES", "IS_GIJON", "gijon-card-images.js", "card-image-fallback.js"]:
    assert forbidden not in app_entry, f"city-specific renderer selection reintroduced: {forbidden}"

runtime_state = (APP / "agenda-runtime-state.mjs").read_text(encoding="utf-8")
assert "eventForCityPresentation(event, cityId)" in runtime_state, "city presentation differences must enter through the adapter boundary"

for module in ["exhibition-hours.js", "public-presentation-guard.js", "card-experience.js", "temporal-priority.js"]:
    text = (APP / module).read_text(encoding="utf-8")
    assert "getAgendaRuntimeSnapshot" in text, f"{module} does not consume the shared runtime snapshot"
    assert "loadAgendaDataset" not in text, f"{module} must not own a parallel data runtime"

exhibition_groups = (APP / "exhibition-groups.js").read_text(encoding="utf-8")
for forbidden in ["groupStandaloneExhibitions", "groupStandaloneCards", "EXHIBITION_GROUP_MIN"]:
    assert forbidden not in exhibition_groups, f"second exhibition grouping authority reintroduced: {forbidden}"
assert "function enhanceCoreGroups()" in exhibition_groups

first_run = runtime_files["first_run"]
assert "window.location.assign" not in first_run
assert "window.location.replace" not in first_run
assert "location.reload" not in first_run
assert not (APP / "gijon-card-images.js").exists(), "city-specific card renderer must stay retired"
assert not (APP / "card-image-fallback.js").exists(), "duplicate card fallback renderer must stay retired"

favorites_core = (ASSETS / "favorites-core.mjs").read_text(encoding="utf-8")
assert "isSafeCityId" in favorites_core
assert 'new Set(["valparaiso", "gijon"])' not in favorites_core

index = (APP / "index.html").read_text(encoding="utf-8")
assert "data-city-options" in index
assert 'data-city-option="valparaiso"' not in index
assert 'data-city-option="gijon"' not in index

service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
assert '"./cities.json"' in service_worker
assert "new URL(city.dataset, self.registration.scope).href" in service_worker

print("THIRD_CITY_ARCHITECTURE_READY")
