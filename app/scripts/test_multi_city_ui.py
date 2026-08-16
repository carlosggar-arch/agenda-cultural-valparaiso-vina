from pathlib import Path

APP = Path("app")
index = (APP / "index.html").read_text(encoding="utf-8")
app_js = (APP / "app.js").read_text(encoding="utf-8")
css = (APP / "app.css").read_text(encoding="utf-8")
city_header_css = (APP / "city-header.css").read_text(encoding="utf-8")
header_redesign_css = (APP / "header-redesign.css").read_text(encoding="utf-8")
header_redesign_js = (APP / "header-redesign.js").read_text(encoding="utf-8")
card_js = (APP / "card-experience.js").read_text(encoding="utf-8")
card_css = (APP / "card-experience.css").read_text(encoding="utf-8")
schedule_display_js = (APP / "schedule-display.js").read_text(encoding="utf-8")
fallback_js = (APP / "card-image-fallback.js").read_text(encoding="utf-8")
compact_js = (APP / "compact-top.js").read_text(encoding="utf-8")
gijon_visual_js = (APP / "gijon-visual-reference.js").read_text(encoding="utf-8")
lean_filters_js = (APP / "lean-filters.js").read_text(encoding="utf-8")
community_source_js = (APP / "community-source.js").read_text(encoding="utf-8")
source_form = (APP / "proponer-fuente.html").read_text(encoding="utf-8")
service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
media_layout = Path("assets/event-media-layout.css").read_text(encoding="utf-8")
schedule_module = Path("assets/event-schedule-display.mjs").read_text(encoding="utf-8")

assert 'data-city-option="valparaiso"' in index
assert 'data-city-option="gijon"' in index
assert 'data-city-switch' in index
assert 'data-use-location' in index
assert 'data-search' in index
assert 'data-section-filters' in index
assert 'data-category-filters' in index
assert 'data-dated-grid' in index
assert 'data-program-grid' in index
assert 'data-flexible-grid' in index
assert 'data-sources-grid' in index
assert 'data-app-version' in index
assert 'data-city-masthead' in index
assert '<strong>¡Vivamos!</strong>' in index

assert 'dataset: "../agenda_web.json"' in app_js
assert 'dataset: "./data/gijon/agenda_web.json"' in app_js
assert 'const STORAGE_KEY = "agenda-cultural-city"' in app_js
assert 'navigator.geolocation' in app_js
assert 'cache: "no-store"' in app_js
assert 'renderCategories()' in app_js
assert 'renderSources()' in app_js
assert 'function eventMatchesSection' in app_js
assert 'function eventMatchesCategory' in app_js

assert '.city-masthead' in city_header_css
assert 'html[data-city="valparaiso"]' in city_header_css
assert 'html[data-city="gijon"]' in city_header_css
assert '.masthead-valpo' in city_header_css
assert '.masthead-gijon' in city_header_css

assert 'header.dataset.headerRedesign = "hero-v3"' in header_redesign_js
assert 'art.className = "header-art"' in header_redesign_js
assert '.header-art' in header_redesign_css
assert './illustrations/valparaiso-header.svg' in header_redesign_css
assert './illustrations/gijon-header.svg' in header_redesign_css

assert 'openEventDetail' in card_js
assert 'event-card-media' in card_js
assert 'event-card-body' in card_js
assert 'event-card-actions' in card_js
assert 'card-day-badge' in card_js
assert 'looksLikeGenericSchedule(event)' in card_js
assert 'MEDIA_STYLESHEET = "../assets/event-media-layout.css?v=20260816"' in card_js
assert '.event-card-media' in card_css
assert 'from "../assets/event-schedule-display.mjs"' in schedule_display_js
assert 'formatSchedule(event.schedule, activeConfig)' in schedule_display_js
assert 'stripMediaControls' in schedule_display_js
assert 'activeCity() !== "valparaiso"' in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js
assert 'object-fit: contain !important' in media_layout
assert '.card-meta-right' in media_layout
assert '.event-card-media > button' in media_layout
assert 'export function formatSchedule' in schedule_module

assert '.hero > h1' in compact_js
assert '.hero > .hero-copy' in compact_js
assert '.search-row' in compact_js
assert 'white-space: normal !important' in compact_js
assert 'flex-wrap: nowrap !important' not in compact_js
assert 'overflow-x: auto !important' not in compact_js
# The dated section is already the main result list, so its redundant heading
# and count stay visually hidden while secondary sections keep their headings.
assert '.content-section[data-dated-section] > .section-heading' in compact_js
assert '.content-section[data-dated-section]' in compact_js
assert '.section-heading p:not(.eyebrow)' in compact_js
assert '.agenda-heading' in compact_js
assert '.app-header' in compact_js
assert 'new Set(["hoy", "fin-de-semana", "terminan-pronto", "gratis", "todos"])' in lean_filters_js
assert 'data-section-filter="todos"' in lean_filters_js
assert "MutationObserver" in lean_filters_js

assert 'https://www.gijon.es/app/actividades/oferta' in gijon_visual_js
assert 'data-gijon-visual-reference' in gijon_visual_js
assert 'Explorar actividades en Gijón' in gijon_visual_js
assert 'grid.prepend(buildVisualReference())' in gijon_visual_js

# Community source proposal stays in the active city and uses the existing review flow.
assert 'proponer-fuente.html' in community_source_js
assert 'data-source-proposal-cta' in community_source_js
assert 'data-community-source-form' in source_form
assert 'cf-turnstile' in source_form
assert 'Enviar para revisión' in source_form

assert "dataset público todavía no ha sido conectado" not in app_js
assert "No pudimos cargar la agenda" in app_js
assert '.quick-sections' in css
assert '.category-filters' in css
assert '.category-chip.active' in css
assert '@media(max-width:560px)' in css
assert '.event-grid,.compact-grid{grid-template-columns:1fr}' in css

assert 'const CACHE_VERSION = "v23";' in service_worker
assert "refreshOpenWindows" in service_worker
assert "client.navigate(client.url)" in service_worker
shell_block = service_worker.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
assert '"./city-header.css"' in shell_block
assert '"./header-redesign.css"' in shell_block
assert '"./vivamos-brand.js"' in shell_block
assert '"./header-redesign.js"' in shell_block
assert '"./card-experience.js"' in shell_block
assert '"./schedule-display.js"' in shell_block
assert '"./card-experience.css"' in shell_block
assert '"./card-image-fallback.js"' in shell_block
assert '"./compact-top.js"' in shell_block
assert '"./gijon-visual-reference.js"' in shell_block
assert '"./lean-filters.js"' in shell_block
assert '"./community-source.js"' in shell_block
assert '"./community-source.css"' in shell_block
assert '"./proponer-fuente.html"' in shell_block
assert '"./proponer-fuente.js"' in shell_block
assert '"./illustrations/valparaiso-header.svg"' in shell_block
assert '"./illustrations/gijon-header.svg"' in shell_block
assert '"../assets/event-media-layout.css"' in shell_block
assert '"../assets/event-schedule-display.mjs"' in shell_block
assert '"../assets/categoria-exposiciones.jpg"' in shell_block

print("Multi-city persistent header, shared schedules, clean media grid and Vivamos brand tests: OK")
