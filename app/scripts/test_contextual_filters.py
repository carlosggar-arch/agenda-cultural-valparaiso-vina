from pathlib import Path

combined = Path("app/combined-filters.js").read_text(encoding="utf-8")
combined_css = Path("app/combined-filters.css").read_text(encoding="utf-8")
advanced = Path("app/search-filter-upgrade.js").read_text(encoding="utf-8")
advanced_css = Path("app/search-filter-upgrade.css").read_text(encoding="utf-8")
polish = Path("app/combined-filters-polish.js").read_text(encoding="utf-8")
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
    "function eventMatchesWhen", "function eventMatchesArea", "function eventMatchesPrice",
    "function eventMatchesCategories", "function eventMatchesQuery",
    'ignore.has("categories")', 'state.categories.has(id)',
    'tokens.every((token) => haystack.includes(token))', 'normalize("NFD")',
    'state.when = "personalizado"', 'history.replaceState', 'url.searchParams.set',
    'currentCityId() !== "valparaiso"', 'forceBaseAppFilters',
):
    assert marker in combined

for marker in (
    'data-smart-search', 'data-combined-when', 'data-combined-area',
    'data-combined-price', 'data-combined-category-filters', 'data-date-from', 'data-date-to',
):
    assert marker in app_index
assert './combined-filters.js' in app_index
assert './contextual-filters.js' not in app_index
assert '.filter-workbench' in combined_css
assert '.custom-date-range' in combined_css
assert '.smart-search' in combined_css
assert '.legacy-filter-hooks' in combined_css
assert '.agenda-heading { display: flex !important;' in polish
assert 'preserveScrollDuringLegacyClick' in polish

for marker in (
    'data-extra-format-value="presencial"', 'data-extra-format-value="online"',
    'data-extra-feature="family"', 'data-extra-feature="registration"',
    'function suggestionCandidates', 'function isFamilyEvent', 'function hasRegistration',
    'url.searchParams.set("features"', 'url.searchParams.set("format"',
):
    assert marker in advanced
assert '.advanced-filter-grid' in advanced_css
assert '.search-suggestions' in advanced_css

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

assert 'const APP_VERSION = "PWA v28"' in pwa
assert 'import "./combined-filters-polish.js";' in pwa
assert 'import "./search-filter-upgrade.js";' in pwa
assert 'const CACHE_VERSION = "v28"' in service_worker
assert '"./combined-filters.js"' in service_worker
assert '"./combined-filters.css"' in service_worker
assert '"./combined-filters-polish.js"' in service_worker
assert '"./search-filter-upgrade.js"' in service_worker
assert '"./search-filter-upgrade.css"' in service_worker
assert "client.navigate(" not in service_worker
assert "refreshOpenWindows" not in service_worker

assert '<div class="mosaic-top"' in root_index
assert '<div class="mosaic-wave"' in root_index
assert '<div class="footer-mosaic"' in root_index
assert './assets/web-event-enhancements.js' in root_index
assert 'window.location.replace(target.href)' not in root_index

assert 'MEDIA_STYLESHEET = "./assets/event-media-layout.css?v=20260816b"' in web_enhancements
assert 'formatSchedule(event?.schedule, SCHEDULE_OPTIONS)' in web_enhancements
assert 'object-fit: contain !important' in media_layout
assert '.event-card-media > button' in media_layout
assert 'export function formatSchedule' in schedule_module
assert 'schedule?.opening_hours' in schedule_module
assert 'from "../assets/event-schedule-display.mjs?v=20260817-hours"' in app_schedule
assert 'formatSchedule(schedule, activeConfig)' in app_schedule
assert 'scheduleForGijonEvent' in app_schedule

print("Combined and advanced filter, source diagnostics, unified schedule/media, independent web and app tests: OK")
