from pathlib import Path

combined = Path("app/combined-filters.js").read_text(encoding="utf-8")
combined_css = Path("app/combined-filters.css").read_text(encoding="utf-8")
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

# Combined filter contract: dimensions AND together, categories are multi-select,
# and search is accent-insensitive token matching rather than one raw substring.
assert "function eventMatchesWhen" in combined
assert "function eventMatchesArea" in combined
assert "function eventMatchesPrice" in combined
assert "function eventMatchesCategories" in combined
assert "function eventMatchesQuery" in combined
assert 'ignore.has("categories")' in combined
assert "state.categories.has(id)" in combined
assert "tokens.every((token) => haystack.includes(token))" in combined
assert "normalize(\"NFD\")" in combined
assert 'state.when = "personalizado"' in combined
assert 'history.replaceState' in combined
assert 'url.searchParams.set' in combined
assert 'currentCityId() !== "valparaiso"' in combined
assert 'data-event-id' in combined
assert 'forceBaseAppFilters' in combined

assert 'data-smart-search' in app_index
assert 'data-combined-when' in app_index
assert 'data-combined-area' in app_index
assert 'data-combined-price' in app_index
assert 'data-combined-category-filters' in app_index
assert 'data-date-from' in app_index
assert 'data-date-to' in app_index
assert './combined-filters.js' in app_index
assert './contextual-filters.js' not in app_index
assert '.filter-workbench' in combined_css
assert '.custom-date-range' in combined_css
assert '.smart-search' in combined_css
assert '.legacy-filter-hooks' in combined_css
assert '.agenda-heading { display: flex !important;' in polish
assert 'preserveScrollDuringLegacyClick' in polish

assert "function enforceQuickFilterVisibility()" in density
assert 'id !== "todos" && count === 0' in density
assert '.quick-sections [data-section-filter][hidden]' in density
assert "white-space: nowrap !important" in density
assert "min-height: 0 !important" in density
assert "width: 62px !important" in density
assert "font-size: 1.52rem !important" in density
assert "font-size: .72rem !important" in density
assert "font-size: clamp(1.55rem, 3.35vw, 3rem) !important" in density
assert "background-position: right 58% !important" in density
assert '@media (min-width: 701px)' in density
assert 'html[data-city="gijon"] .app-header .header-art' in density
assert "width: 62% !important" in density
assert "opacity: .74 !important" in density
assert "background-size: 78% auto !important" in density
assert "background-repeat: no-repeat !important" in density
assert "background-position: right 38% !important" in density
assert "#000 18%" in density
assert "font-size: 1.18rem !important" in density
assert "font-size: .62rem !important" in density
assert "grid-template-columns: repeat(3, minmax(0, 1fr)) !important" in density

assert 'id="gijon-boat"' in gijon_svg
assert 'scale(1.45)' in gijon_svg
assert 'opacity="0.96"' in gijon_svg

assert "function sourceDiagnosticText(source)" in sources_toggle
assert 'if (value === null || value === undefined || value === "") return null;' in sources_toggle
assert "reviewed_items" in sources_toggle
assert "filtered_or_deduplicated" in sources_toggle
assert "without_start_time" in sources_toggle
assert "source_diagnostics" in sources_toggle
assert "cinearte_vina" in sources_toggle
assert "insomniacine" in sources_toggle

assert 'const APP_VERSION = "PWA v26"' in pwa
assert 'import "./combined-filters-polish.js";' in pwa
assert 'const CACHE_VERSION = "v26"' in service_worker
assert '"./combined-filters.js"' in service_worker
assert '"./combined-filters.css"' in service_worker
assert '"./combined-filters-polish.js"' in service_worker
assert "client.navigate(" not in service_worker
assert "refreshOpenWindows" not in service_worker

# The root website remains the independent Valparaíso/Viña web experience;
# the multi-city PWA remains available independently under /app/.
assert '<div class="mosaic-top"' in root_index
assert '<div class="mosaic-wave"' in root_index
assert '<div class="footer-mosaic"' in root_index
assert './assets/web-event-enhancements.js' in root_index
assert 'window.location.replace(target.href)' not in root_index

# WEB and APP share one non-cropping event-media contract.
assert 'MEDIA_STYLESHEET = "./assets/event-media-layout.css?v=20260816b"' in web_enhancements
assert 'compactScheduleDayLabel' in web_enhancements
assert 'formatSchedule(event?.schedule, SCHEDULE_OPTIONS)' in web_enhancements
assert 'removeMediaOverlays' in web_enhancements
assert 'looksLikeGenericSchedule(event)' in web_enhancements
assert 'card-day-badge' in web_enhancements
assert 'object-fit: contain !important' in media_layout
assert 'filter: blur(18px)' in media_layout
assert '.card-media > button' in media_layout
assert '.event-card-media > button' in media_layout
assert '.card-topline,' in media_layout
assert '.event-card-body .card-meta-row' in media_layout

# One formatter owns final schedule rendering in WEB and APP.
assert 'export function formatSchedule' in schedule_module
assert 'schedule?.opening_time' in schedule_module
assert 'schedule?.opening_hours' in schedule_module
assert 'Cerrado hoy' in schedule_module
assert 'from "../assets/event-schedule-display.mjs?v=20260817-hours"' in app_schedule
assert 'formatSchedule(schedule, activeConfig)' in app_schedule
assert 'scheduleForGijonEvent' in app_schedule

print("Combined filter, source diagnostics, unified schedule/media, independent web and app tests: OK")
