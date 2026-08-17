from pathlib import Path

combined = Path("app/combined-filters.js").read_text(encoding="utf-8")
combined_css = Path("app/combined-filters.css").read_text(encoding="utf-8")
polish = Path("app/combined-filters-polish.js").read_text(encoding="utf-8")
compact = Path("app/compact-top.css").read_text(encoding="utf-8")
compact_js = Path("app/compact-top.js").read_text(encoding="utf-8")
density = Path("app/density-polish.js").read_text(encoding="utf-8")
gijon_svg = Path("app/illustrations/gijon-header.svg").read_text(encoding="utf-8")
sources_toggle = Path("app/sources-toggle.js").read_text(encoding="utf-8")
pwa = Path("app/pwa.js").read_text(encoding="utf-8")
service_worker = Path("app/service-worker.js").read_text(encoding="utf-8")
root_index = Path("index.html").read_text(encoding="utf-8")
app_index = Path("app/index.html").read_text(encoding="utf-8")
web_enhancements = Path("assets/web-event-enhancements.js").read_text(encoding="utf-8")
media_layout = Path("assets/event-media-layout.css").read_text(encoding="utf-8")
schedule_module = Path("assets/event-schedule-display.mjs").read_text(encoding="utf-8")
app_schedule = Path("app/schedule-display.js").read_text(encoding="utf-8")

for marker in (
    "function eventMatchesWhen", "function eventMatchesArea",
    "function eventMatchesAccess", "function eventMatchesFormat",
    "function eventMatchesAudience", "function eventMatchesCategories",
    "function eventMatchesQuery", "function derivedSearchTerms",
    "const SEARCH_ALIASES", "function queryAlternatives",
    'ignore.has("access")', 'ignore.has("format")', 'ignore.has("audience")',
    'state.categories.has(id)', 'queryAlternatives(token)', 'normalize("NFD")',
    'state.when = "personalizado"', 'history.replaceState', 'url.searchParams.set',
    'setOrDelete("access"', 'setOrDelete("format"', 'setOrDelete("aud"',
    'url.searchParams.delete("price")', 'currentCityId() !== "valparaiso"',
    'forceBaseAppFilters', 'state.query ? "Resultados de búsqueda"',
):
    assert marker in combined
assert "function eventMatchesPrice" not in combined

for marker in (
    'data-smart-search', 'data-combined-when', 'data-combined-area',
    'data-combined-category-filters', 'data-date-from', 'data-date-to',
):
    assert marker in app_index
for removed in ('data-combined-price', 'data-combined-access', 'data-combined-format', 'data-combined-audience'):
    assert removed not in app_index
assert '["access", "format", "aud"]' in app_index
assert './combined-filters.js' in app_index
assert './contextual-filters.js' not in app_index
assert '<link rel="stylesheet" href="./compact-top.css">' in app_index
assert '<link rel="stylesheet" href="./header-redesign.css">' in app_index
assert app_index.index('./compact-top.css') < app_index.index('./header-redesign.css') < app_index.index('</head>')
assert '.filter-workbench' in combined_css
assert '.custom-date-range' in combined_css
assert '.smart-search' in combined_css
assert '.legacy-filter-hooks' in combined_css
assert '.event-card[hidden]{display:none!important}' in combined_css

assert 'function removeNonActionableFilterCopy()' in polish
assert 'document.querySelector(selector)?.remove()' in polish
assert 'function removePriceFilter()' in polish
assert 'function clearRemovedFilterState()' in polish
assert '["price", "access", "format", "aud"]' in polish
assert '["when", "area", "cat", "q", "from", "to"]' in polish
assert 'function queueFilterResync()' in polish
assert 'new MutationObserver(queueFilterResync)' in polish
assert '.discovery-heading { display: flex !important;' not in polish
assert '.category-filter-panel .category-explorer-heading { display: flex !important;' not in polish
assert '.agenda-heading { display: flex !important;' not in polish

assert '.filter-workbench {' in compact
assert 'padding: 0 !important;' in compact
assert 'border: 0 !important;' in compact
assert 'background: transparent !important;' in compact
assert '.filter-workbench::before {' in compact
assert 'url("../assets/mosaic-top.png")' in compact
assert '.filter-group {' in compact
assert 'padding: .24rem 0 !important;' in compact
assert '[data-combined-when] {' in compact
assert 'padding-top: 1.55rem !important;' in compact
assert '[data-combined-when]::before {' in compact
assert 'content: "Cuándo";' in compact
assert '.filter-choice {' in compact
assert 'padding: .32rem .46rem !important;' in compact
assert '.category-filters {' in compact
assert 'minmax(116px, 1fr)' in compact
assert '@media (max-width: 560px)' in compact
assert 'flex-wrap: nowrap !important;' in compact
assert 'document.createElement("style")' not in compact_js
assert 'style.textContent' not in compact_js

assert "function enforceQuickFilterVisibility()" in density
assert 'id !== "todos" && count === 0' in density
assert '.quick-sections [data-section-filter][hidden]' in density
assert 'html[data-city="gijon"] .app-header .header-art' in density
assert 'id="gijon-boat"' in gijon_svg
assert 'scale(1.45)' in gijon_svg

assert "function sourceDiagnosticText(source)" in sources_toggle
assert "reviewed_items" in sources_toggle
assert "source_diagnostics" in sources_toggle
assert "cinearte_vina" in sources_toggle
assert "insomniacine" in sources_toggle

assert 'const APP_VERSION = "PWA v33"' in pwa
assert 'import "./combined-filters-polish.js";' in pwa
assert 'import "./plan-ahead.js";' in pwa
assert 'import "./favorites.js";' in pwa
assert 'const CACHE_VERSION = "v37"' in service_worker
assert '"./combined-filters.js"' in service_worker
assert '"./combined-filters.css"' in service_worker
assert '"./combined-filters-polish.js"' in service_worker
assert '"./compact-top.css"' in service_worker
assert '"./plan-ahead.js"' in service_worker
assert '"./favorites.js"' in service_worker
assert '"../assets/plan-ahead-core.mjs"' in service_worker
assert '"../assets/plan-ahead.css"' in service_worker
assert '"../assets/favorites-core.mjs"' in service_worker
assert '"../assets/favorites-view.mjs"' in service_worker
assert '"../assets/favorites.css"' in service_worker
assert "client.navigate(" not in service_worker
assert "refreshOpenWindows" not in service_worker

assert '<div class="mosaic-top"' in root_index
assert '<div class="mosaic-wave"' in root_index
assert '<div class="footer-mosaic"' in root_index
assert './assets/web-event-enhancements.js' in root_index
assert 'window.location.replace(target.href)' not in root_index

assert 'MEDIA_STYLESHEET = "./assets/event-media-layout.css?v=20260816b"' in web_enhancements
assert 'formatSchedule(event?.schedule, SCHEDULE_OPTIONS)' in web_enhancements
assert './plan-ahead-web.js?v=20260817' in web_enhancements
assert './favorites-web.js?v=20260817' in web_enhancements
assert 'object-fit: contain !important' in media_layout
assert '.event-card-media > button' in media_layout
assert 'export function formatSchedule' in schedule_module
assert 'schedule?.opening_hours' in schedule_module
assert 'from "../assets/event-schedule-display.mjs?v=20260817-hours"' in app_schedule
assert 'formatSchedule(schedule, activeConfig)' in app_schedule
assert 'scheduleForGijonEvent' in app_schedule

print("Semantic search plus compact filters, plan-ahead and favorites with PWA cache v36: OK")