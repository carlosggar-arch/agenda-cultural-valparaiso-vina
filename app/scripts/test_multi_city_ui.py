import json
from pathlib import Path

APP = Path("app")
ASSETS = Path("assets")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


index = read(APP / "index.html")
app_entry = read(APP / "app.js")
app_core = read(APP / "app-core.js")
city_first_run = read(APP / "city-first-run.js")
city_registry_module = read(ASSETS / "city-registry.mjs")
city_registry = json.loads(read(APP / "cities.json"))
combined = read(APP / "combined-filters.js")
card_js = read(APP / "card-experience.js")
image_guard_js = read(APP / "image-quality-guard.js")
schedule_display_js = read(APP / "schedule-display.js")
runtime_state = read(APP / "agenda-runtime-state.mjs")
render_lifecycle = read(APP / "render-lifecycle.js")
service_worker = read(APP / "service-worker.js")
shell_manifest = read(APP / "service-worker-assets.generated.js")
pwa = read(APP / "pwa.js")

# The shell exposes one registry-driven city chooser and one set of shared
# discovery controls. City choices themselves are not hard-coded in HTML.
for marker in (
    "data-city-options",
    "data-city-switch",
    "data-use-location",
    "data-smart-search",
    "data-combined-when",
    "data-combined-area",
    "data-combined-category-filters",
    "data-dated-grid",
    "data-program-grid",
    "data-flexible-grid",
):
    assert marker in index
assert 'data-city-option="valparaiso"' not in index
assert 'data-city-option="gijon"' not in index

city_ids = {city["id"] for city in city_registry["cities"]}
assert city_registry["default_city"] in city_ids
assert {"valparaiso", "gijon"}.issubset(city_ids)
for marker in (
    "export const CITY_STORAGE_KEY",
    "export function loadCityRegistry",
    "function validateRegistry",
    "export function cityFromRegistry",
):
    assert marker in city_registry_module

# app-core owns city changes and reloads only data/UI state, never the document.
assert "loadCityRegistry" in app_core
assert "const CITIES = CITY_REGISTRY.byId" in app_core
assert "async function loadCity(id)" in app_core
assert "loadAgendaDataset(city)" in app_core
assert "button.dataset.cityOption" in app_core
assert "loadCity(button.dataset.cityOption)" in app_core
for forbidden in ("window.location.assign", "window.location.replace", "location.reload"):
    assert forbidden not in city_first_run

# All presentation that is not intrinsically city-specific belongs to one common
# runtime. The entrypoint must not select renderers based on a concrete city.
common_runtime = app_entry.split("const OPTIONAL_MODULES = [", 1)[1].split("];", 1)[0]
for module in (
    "temporal-priority.js",
    "exhibition-groups.js",
    "schedule-display.js",
    "event-card-data-quality.mjs",
    "exhibition-hours.js",
    "card-experience.js",
    "public-presentation-guard.js",
    "image-quality-guard.js",
):
    assert module in common_runtime, f"{module} must belong to the common runtime"
for forbidden in ("IS_GIJON", "GIJON_DEFERRED_MODULES", "gijon-card-images.js", "card-image-fallback.js"):
    assert forbidden not in app_entry
assert not (APP / "gijon-card-images.js").exists()
assert not (APP / "card-image-fallback.js").exists()

# Shared renderers consume the normalized/adapted snapshot. Concrete city
# differences belong at the adapter/data boundary, not in card/schedule modules.
for name, source in (
    ("card-experience", card_js),
    ("image-quality-guard", image_guard_js),
    ("schedule-display", schedule_display_js),
):
    assert "getAgendaRuntimeSnapshot" in source, f"{name} must consume shared runtime state"
    assert "loadAgendaDataset" not in source, f"{name} must not own a parallel data runtime"
    assert "new MutationObserver" not in source, f"{name} must use explicit lifecycle events"
assert "scheduleForGijonEvent" not in schedule_display_js
assert "gijonLocationForEvent" not in schedule_display_js
assert "eventForCityPresentation" in runtime_state
assert "presentationEvents" in runtime_state
assert "vivamos:agenda-data-ready" in runtime_state
assert "vivamos:agenda-rendered" in render_lifecycle
assert "subtree: true" not in render_lifecycle
assert "characterData: true" not in render_lifecycle

# Filtering remains registry/data driven and participates in the same normalized
# pipeline instead of fetching a separate presentation dataset.
assert "loadAgendaDataset" in combined
assert "function eventMatchesWhen" in combined
assert "function eventMatchesArea" in combined
assert "function eventMatchesCategories" in combined
assert "function eventMatchesQuery" in combined

# PWA enhancement code must not instantiate content presentation modules a
# second time. app.js owns them; the service worker only caches their assets.
for marker in (
    '"./card-experience.js"',
    '"./image-quality-guard.js"',
    '"./event-card-data-quality.mjs"',
    '"./public-presentation-guard.js"',
    '"./schedule-display.js',
    '"./exhibition-hours.js',
    '"./exhibition-groups.js',
):
    assert marker not in pwa

assert 'importScripts("./release-version.js", "./service-worker-assets.generated.js")' in service_worker
assert "clients.claim()" in service_worker
assert "client.navigate(" not in service_worker
assert "refreshOpenWindows" not in service_worker
assert 'const CITY_REGISTRY_URL = new URL("./cities.json", self.registration.scope).href' in service_worker
assert "async function datasetUrls()" in service_worker
assert "async function warmDatasetCache()" in service_worker

for asset in (
    "./cities.json",
    "../assets/city-registry.mjs",
    "./agenda-runtime-state.mjs",
    "./render-lifecycle.js",
    "./card-experience.js",
    "./image-quality-guard.js",
    "./event-card-data-quality.mjs",
    "./schedule-display.js",
    "./exhibition-hours.js",
    "./exhibition-groups.js",
    "./public-presentation-guard.js",
):
    assert f'"{asset}"' in shell_manifest, f"generated shell missing {asset}"

print("Multi-city registry, in-place city switching, shared presentation runtime and generated-shell contracts: OK")
