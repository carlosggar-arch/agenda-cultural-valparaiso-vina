from pathlib import Path

APP = Path("app")
index = (APP / "index.html").read_text(encoding="utf-8")
app_js = (APP / "app.js").read_text(encoding="utf-8")
css = (APP / "app.css").read_text(encoding="utf-8")
combined = (APP / "combined-filters.js").read_text(encoding="utf-8")
combined_css = (APP / "combined-filters.css").read_text(encoding="utf-8")
city_header_css = (APP / "city-header.css").read_text(encoding="utf-8")
header_redesign_css = (APP / "header-redesign.css").read_text(encoding="utf-8")
header_redesign_js = (APP / "header-redesign.js").read_text(encoding="utf-8")
card_js = (APP / "card-experience.js").read_text(encoding="utf-8")
card_css = (APP / "card-experience.css").read_text(encoding="utf-8")
schedule_display_js = (APP / "schedule-display.js").read_text(encoding="utf-8")
fallback_js = (APP / "card-image-fallback.js").read_text(encoding="utf-8")
compact_js = (APP / "compact-top.js").read_text(encoding="utf-8")
gijon_visual_js = (APP / "gijon-visual-reference.js").read_text(encoding="utf-8")
sources_toggle_js = (APP / "sources-toggle.js").read_text(encoding="utf-8")
community_source_js = (APP / "community-source.js").read_text(encoding="utf-8")
source_form = (APP / "proponer-fuente.html").read_text(encoding="utf-8")
pwa = (APP / "pwa.js").read_text(encoding="utf-8")
service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
media_layout = Path("assets/event-media-layout.css").read_text(encoding="utf-8")
schedule_module = Path("assets/event-schedule-display.mjs").read_text(encoding="utf-8")

for marker in (
    'data-city-option="valparaiso"', 'data-city-option="gijon"', 'data-city-switch',
    'data-use-location', 'data-search', 'data-smart-search', 'data-section-filters',
    'data-category-filters', 'data-combined-when', 'data-combined-area',
    'data-combined-price', 'data-combined-category-filters', 'data-date-from',
    'data-date-to', 'data-dated-grid', 'data-program-grid', 'data-flexible-grid',
    'data-sources-grid', 'data-app-version', 'data-city-masthead',
):
    assert marker in index
assert '<strong>¡Vivamos!</strong>' in index
assert './combined-filters.css' in index
assert './combined-filters.js' in index
assert './contextual-filters.js' not in index

assert 'dataset: "../agenda_web.json"' in app_js
assert 'dataset: "./data/gijon/agenda_web.json"' in app_js
assert 'const STORAGE_KEY = "agenda-cultural-city"' in app_js
assert 'navigator.geolocation' in app_js
assert 'cache: "no-store"' in app_js
assert 'renderCategories()' in app_js
assert 'renderSources()' in app_js

for marker in (
    'function eventMatchesWhen', 'function eventMatchesArea', 'function eventMatchesPrice',
    'function eventMatchesCategories', 'function eventMatchesQuery',
    'tokens.every((token) => haystack.includes(token))', 'state.categories = new Set',
    'history.replaceState', 'url.searchParams.set', 'forceBaseAppFilters',
):
    assert marker in combined
assert 'currentCityId() !== "valparaiso"' in combined
assert '.filter-workbench' in combined_css
assert '.filter-grid' in combined_css
assert '.custom-date-range' in combined_css
assert '.smart-search' in combined_css
assert '.legacy-filter-hooks{display:none!important}' in combined_css

assert '.city-masthead' in city_header_css
assert 'html[data-city="valparaiso"]' in city_header_css
assert 'html[data-city="gijon"]' in city_header_css
assert 'header.dataset.headerRedesign = "hero-v3"' in header_redesign_js
assert 'art.className = "header-art"' in header_redesign_js
assert '.header-art' in header_redesign_css

assert 'openEventDetail' in card_js
assert 'event-card-media' in card_js
assert 'event-card-actions' in card_js
assert 'card-day-badge' in card_js
assert 'looksLikeGenericSchedule(event)' in card_js
assert '.event-card-media' in card_css
assert 'formatSchedule(schedule, activeConfig)' in schedule_display_js
assert 'scheduleForGijonEvent' in schedule_display_js
assert 'activeCity() !== "valparaiso"' in fallback_js
assert 'object-fit: contain !important' in media_layout
assert 'export function formatSchedule' in schedule_module

assert '.hero > h1' in compact_js
assert '.agenda-heading' in compact_js
assert 'const PUBLIC_CATALOGUES = Object.freeze' in sources_toggle_js
assert 'valparaiso: "../fuentes_publicas.json"' in sources_toggle_js
assert 'authoritativeCatalogue' in sources_toggle_js
assert 'https://www.gijon.es/app/actividades/oferta' in gijon_visual_js
assert 'proponer-fuente.html' in community_source_js
assert 'data-community-source-form' in source_form
assert '.quick-sections' in css
assert '.category-filters' in css

assert 'const APP_VERSION = "PWA v27"' in pwa
assert 'import "./combined-filters-polish.js";' in pwa
assert 'import "./lean-filters.js";' not in pwa
assert 'const CACHE_VERSION = "v27";' in service_worker
assert "clients.claim()" in service_worker
assert "client.navigate(" not in service_worker
assert "refreshOpenWindows" not in service_worker
shell_block = service_worker.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
for asset in (
    '"./combined-filters.css"', '"./combined-filters.js"', '"./combined-filters-polish.js"',
    '"./city-header.css"', '"./header-redesign.css"', '"./card-experience.js"',
    '"./schedule-display.js"', '"./gijon-venue-hours.js"', '"./event-detail.js"',
    '"./sources-toggle.js"', '"./community-source.js"', '"../assets/event-media-layout.css"',
    '"../assets/event-schedule-display.mjs"',
):
    assert asset in shell_block
assert '"./lean-filters.js"' not in shell_block
assert '"./contextual-filters.js"' not in shell_block

print("Multi-city combined search/filter UI, shared schedules and stable PWA activation tests: OK")
