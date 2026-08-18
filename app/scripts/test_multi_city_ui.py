import json
from pathlib import Path

APP = Path("app")
index = (APP / "index.html").read_text(encoding="utf-8")
app_js = (APP / "app.js").read_text(encoding="utf-8")
app_js += "\n" + (APP / "app-core.js").read_text(encoding="utf-8")
city_first_run = (APP / "city-first-run.js").read_text(encoding="utf-8")
city_registry_module = Path("assets/city-registry.mjs").read_text(encoding="utf-8")
city_registry = json.loads((APP / "cities.json").read_text(encoding="utf-8"))
css = (APP / "app.css").read_text(encoding="utf-8")
combined = (APP / "combined-filters.js").read_text(encoding="utf-8")
combined_css = (APP / "combined-filters.css").read_text(encoding="utf-8")
polish = (APP / "combined-filters-polish.js").read_text(encoding="utf-8")
city_header_css = (APP / "city-header.css").read_text(encoding="utf-8")
header_redesign_css = (APP / "header-redesign.css").read_text(encoding="utf-8")
header_redesign_js = (APP / "header-redesign.js").read_text(encoding="utf-8")
card_js = (APP / "card-experience.js").read_text(encoding="utf-8")
card_css = (APP / "card-experience.css").read_text(encoding="utf-8")
schedule_display_js = (APP / "schedule-display.js").read_text(encoding="utf-8")
fallback_js = (APP / "card-image-fallback.js").read_text(encoding="utf-8")
compact_css = (APP / "compact-top.css").read_text(encoding="utf-8")
compact_js = (APP / "compact-top.js").read_text(encoding="utf-8")
gijon_visual_js = (APP / "gijon-visual-reference.js").read_text(encoding="utf-8")
sources_toggle_js = (APP / "sources-toggle.js").read_text(encoding="utf-8")
community_source_js = (APP / "community-source.js").read_text(encoding="utf-8")
source_form = (APP / "proponer-fuente.html").read_text(encoding="utf-8")
pwa = (APP / "pwa.js").read_text(encoding="utf-8")
plan_ahead = (APP / "plan-ahead.js").read_text(encoding="utf-8")
favorites = (APP / "favorites.js").read_text(encoding="utf-8")
mis_planes = (APP / "mis-planes.html").read_text(encoding="utf-8")
service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
media_layout = Path("assets/event-media-layout.css").read_text(encoding="utf-8")
schedule_module = Path("assets/event-schedule-display.mjs").read_text(encoding="utf-8")
plan_ahead_core = Path("assets/plan-ahead-core.mjs").read_text(encoding="utf-8")
plan_ahead_css = Path("assets/plan-ahead.css").read_text(encoding="utf-8")
favorites_core = Path("assets/favorites-core.mjs").read_text(encoding="utf-8")
favorites_view = Path("assets/favorites-view.mjs").read_text(encoding="utf-8")
favorites_reminders = Path("assets/favorites-reminders.mjs").read_text(encoding="utf-8")
favorites_css = Path("assets/favorites.css").read_text(encoding="utf-8")

for marker in (
    'data-city-options', 'data-city-switch',
    'data-use-location', 'data-search', 'data-smart-search', 'data-section-filters',
    'data-category-filters', 'data-combined-when', 'data-combined-area',
    'data-combined-category-filters', 'data-date-from', 'data-date-to',
    'data-dated-grid', 'data-program-grid', 'data-flexible-grid',
    'data-sources-grid', 'data-app-version', 'data-city-masthead',
):
    assert marker in index
for removed in ('data-combined-price', 'data-combined-access', 'data-combined-format', 'data-combined-audience'):
    assert removed not in index
assert '<strong>¡Vivamos!</strong>' in index
assert './combined-filters.css' in index
assert './combined-filters-bootstrap.js' in index
assert './contextual-filters.js' not in index
assert 'new URLSearchParams(window.location.search).get("city")' in index
assert '["access", "format", "aud"]' in index
assert 'window.__agendaInitialCityPreference' in index
assert '<script type="module" src="./city-first-run.js"></script>' in index

city_ids = {city["id"] for city in city_registry["cities"]}
assert city_registry["default_city"] == "valparaiso"
assert {"valparaiso", "gijon"}.issubset(city_ids)
city_by_id = {city["id"]: city for city in city_registry["cities"]}
assert city_by_id["valparaiso"]["dataset"] == "../agenda_web.json"
assert city_by_id["gijon"]["dataset"] == "./data/gijon/agenda_web.json"
for marker in (
    'export const CITY_STORAGE_KEY = "agenda-cultural-city"',
    'export function loadCityRegistry',
    'function validateRegistry',
    'export function cityFromRegistry',
):
    assert marker in city_registry_module

for marker in (
    'loadCityRegistry',
    'const SUPPORTED_CITIES = new Set(CITY_REGISTRY.cities.map((city) => city.id))',
    'window.__agendaInitialCityPreference',
    'localStorage.removeItem(STORAGE_KEY)',
    'navigator.permissions.query({ name: "geolocation" })',
    'permission.state === "granted"',
    'dataset.selectionRequired = "true"',
    'cityOptions?.addEventListener("click"',
    'event.stopImmediatePropagation()',
):
    assert marker in city_first_run

compact_link = '<link rel="stylesheet" href="./compact-top.css">'
header_link = '<link rel="stylesheet" href="./header-redesign.css?v=20260817-brandicon1">'
assert compact_link in index
assert header_link in index
assert index.index(compact_link) < index.index(header_link) < index.index("</head>")
assert index.index("</head>") < index.index('<script type="module" src="./pwa.js"></script>')
assert 'document.createElement("style")' not in compact_js
assert 'style.textContent' not in compact_js

for marker in (
    'CITY_STORAGE_KEY, loadCityRegistry',
    'const CITY_REGISTRY = await loadCityRegistry()',
    'const CITIES = CITY_REGISTRY.byId',
    'const DEFAULT_CITY_ID = CITY_REGISTRY.defaultCityId',
    'function renderCityOptions()',
    'button.dataset.cityOption = city.id',
    'fetch(city.dataset',
    'cache: "no-store"',
    'renderCategories()',
    'renderSources()',
):
    assert marker in app_js
assert 'navigator.geolocation' in app_js
assert 'function suggestCityFromCoordinates' in app_js

for marker in (
    'function eventMatchesWhen', 'function eventMatchesArea',
    'function eventMatchesAccess', 'function eventMatchesFormat',
    'function eventMatchesAudience', 'function eventMatchesCategories',
    'function eventMatchesQuery', 'function derivedSearchTerms',
    'queryAlternatives(token)', 'state.categories = new Set',
    'history.replaceState', 'url.searchParams.set', 'forceBaseAppFilters',
):
    assert marker in combined
assert 'function eventMatchesPrice' not in combined
assert 'currentCityId() !== "valparaiso"' in combined
assert '.filter-workbench' in combined_css
assert '.filter-grid' in combined_css
assert '.custom-date-range' in combined_css
assert '.smart-search' in combined_css
assert '.legacy-filter-hooks{display:none!important}' in combined_css
assert '.event-card[hidden]{display:none!important}' in combined_css
assert 'function removeNonActionableFilterCopy()' in polish
assert 'function removePriceFilter()' in polish
assert 'function clearRemovedFilterState()' in polish
assert '["price", "access", "format", "aud"]' in polish
assert '["when", "area", "cat", "q", "from", "to"]' in polish
assert 'function queueFilterResync()' in polish
assert '.agenda-heading { display: flex !important;' not in polish

assert '.city-masthead' in city_header_css
assert 'html[data-city="valparaiso"]' in city_header_css
assert 'html[data-city="gijon"]' in city_header_css
assert 'const HEADER_STYLESHEET = "./header-redesign.css?v=20260817-brandicon1"' in header_redesign_js
assert 'header.dataset.headerRedesign = "hero-v4-mobile-direct-actions"' in header_redesign_js
assert 'art.className = "header-art"' in header_redesign_js
assert '.header-art' in header_redesign_css

assert 'openEventDetail' in card_js
assert 'event-card-media' in card_js
assert 'event-card-actions' in card_js
assert 'card-day-badge' in card_js
assert 'looksLikeGenericSchedule(event)' in card_js
assert 'event?.image?.url' in card_js
assert 'image.dataset.eventImage = "relevant"' in card_js
assert '.event-card-media' in card_css
assert 'formatSchedule(schedule, activeConfig)' in schedule_display_js
assert 'scheduleForGijonEvent' in schedule_display_js
assert 'activeCity() !== "valparaiso"' not in fallback_js
assert 'document.querySelectorAll(".event-card-media--placeholder")' in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js
assert 'object-fit: contain !important' in media_layout
assert 'export function formatSchedule' in schedule_module

assert '.hero > h1' in compact_css
assert '.agenda-heading' in compact_css
assert 'padding: 0 !important;' in compact_css
assert 'background: transparent !important;' in compact_css
assert '.filter-workbench::before {' in compact_css
assert 'url("../assets/mosaic-top.png")' in compact_css
assert '[data-combined-when]::before {' in compact_css
assert 'const PUBLIC_CATALOGUES = Object.freeze' in sources_toggle_js
assert 'valparaiso: "../fuentes_publicas.json"' in sources_toggle_js
assert 'authoritativeCatalogue' in sources_toggle_js
assert 'https://www.gijon.es/app/actividades/oferta' in gijon_visual_js
assert 'proponer-fuente.html' in community_source_js
assert 'data-community-source-form' in source_form
assert '.quick-sections' in css
assert '.category-filters' in css

assert 'globalThis.__VIVAMOS_RELEASE__' in pwa
assert 'const APP_VERSION = `PWA v${APP_RELEASE}`;' in pwa
assert 'service-worker.js?v=${APP_RELEASE}' in pwa
assert 'import "./header-redesign.js?v=20260817-brandicon2";' in pwa
assert 'import "./combined-filters-polish.js";' in pwa
assert 'import "./plan-ahead.js";' in pwa
assert 'import "./favorites.js";' in pwa
assert 'import "./lean-filters.js";' not in pwa
assert 'function showInstallHelp()' in pwa
assert 'Añadir a pantalla de inicio' in pwa
assert 'beforeinstallprompt' in pwa
assert 'loadCityRegistry' in plan_ahead
assert 'const CONFIG = CITY_REGISTRY.byId' in plan_ahead
assert 'fetch(config.dataset' in plan_ahead
assert 'Planifica con anticipación' in plan_ahead
assert 'selectPlanAhead' in plan_ahead
assert 'article.dataset.eventId' in plan_ahead
assert 'new MutationObserver' in plan_ahead
assert 'minDays: 14' in plan_ahead_core
assert 'maxDays: 56' in plan_ahead_core
assert 'Inscripción abierta' in plan_ahead_core
assert 'Reserva disponible' in plan_ahead_core
assert 'Entradas disponibles' in plan_ahead_core
assert 'Cupos limitados' in plan_ahead_core
assert '.plan-ahead-grid' in plan_ahead_css

assert 'agenda-cultural-favorites-v1' in favorites_core
assert 'export function toggleFavorite' in favorites_core
assert 'export function favoritesForCity' in favorites_core
assert 'buildFavoriteToggle' in favorites_view
assert 'buildMyPlansSection' in favorites_view
assert 'reminderOptionsForEvent' in favorites_view
assert 'downloadReminderIcs' in favorites_view
assert 'Mis planes' in favorites_view
assert 'loadCityRegistry' in favorites
assert 'const CONFIG = CITY_REGISTRY.byId' in favorites
assert 'fetch(CONFIG[city].dataset' in favorites
assert 'dialog[data-event-detail]' in favorites
assert 'data-favorite-toggle' in favorites
assert 'export function buildReminderIcs' in favorites_reminders
assert 'BEGIN:VALARM' in favorites_reminders
assert 'TRIGGER:${option.trigger}' in favorites_reminders
assert 'favorites-view.mjs?v=20260817-reminders' in mis_planes
assert 'favorites.css?v=20260817-compact-reminders' in mis_planes
assert '.my-plans-section' in favorites_css
assert '.favorite-toggle' in favorites_css
assert '.my-plan-reminder' in favorites_css

assert 'importScripts("./release-version.js")' in service_worker
assert 'const CACHE_VERSION = `v${RELEASE}`;' in service_worker
assert "clients.claim()" in service_worker
assert "client.navigate(" not in service_worker
assert "refreshOpenWindows" not in service_worker
assert 'const CITY_REGISTRY_URL = new URL("./cities.json", self.registration.scope).href' in service_worker
assert 'async function datasetUrls()' in service_worker
assert 'new URL("../agenda_web.json", self.registration.scope).href' in service_worker
assert 'new URL("./data/gijon/agenda_web.json", self.registration.scope).href' in service_worker
assert 'async function warmDatasetCache()' in service_worker
assert 'await datasetUrls()' in service_worker
assert 'await warmDatasetCache()' in service_worker
assert '"./city-first-run.js"' in service_worker
shell_block = service_worker.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
for asset in (
    '"./release-version.js"', '"./cities.json"', '"../assets/city-registry.mjs"',
    '"./combined-filters.css"', '"./combined-filters.js"', '"./combined-filters-polish.js"',
    '"./city-header.css"', '"./compact-top.css"', '"./header-redesign.css?v=20260817-brandicon1"',
    '"./header-redesign.js?v=20260817-brandicon2"', '"./card-experience.js"',
    '"./schedule-display.js"', '"./gijon-venue-hours.js"', '"./event-detail.js"', '"./plan-ahead.js"',
    '"./favorites.js"', '"./mis-planes.html"', '"./sources-toggle.js"', '"./community-source.js"',
    '"../assets/event-media-layout.css"', '"../assets/event-schedule-display.mjs"',
    '"../assets/plan-ahead-core.mjs"', '"../assets/plan-ahead.css"',
    '"../assets/favorites-core.mjs"', '"../assets/favorites-view.mjs"', '"../assets/favorites-reminders.mjs"',
    '"../assets/favorites.css"',
):
    assert asset in shell_block
assert '"./lean-filters.js"' not in shell_block
assert '"./contextual-filters.js"' not in shell_block

print("Multi-city shared-release, shared-registry, Mis planes reminders, install and offline contracts: OK")
