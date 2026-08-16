from pathlib import Path

index = Path("app/index.html").read_text(encoding="utf-8")
app_js = Path("app/app.js").read_text(encoding="utf-8")
pwa_js = Path("app/pwa.js").read_text(encoding="utf-8")
css = Path("app/app.css").read_text(encoding="utf-8")
card_js = Path("app/card-experience.js").read_text(encoding="utf-8")
card_css = Path("app/card-experience.css").read_text(encoding="utf-8")
fallback_js = Path("app/card-image-fallback.js").read_text(encoding="utf-8")
compact_js = Path("app/compact-top.js").read_text(encoding="utf-8")
gijon_visual_js = Path("app/gijon-visual-reference.js").read_text(encoding="utf-8")
lean_filters_js = Path("app/lean-filters.js").read_text(encoding="utf-8")
service_worker = Path("app/service-worker.js").read_text(encoding="utf-8")

required_index_markers = (
    "data-dated-section",
    "data-dated-grid",
    "data-program-section",
    "data-program-grid",
    "data-flexible-section",
    "data-flexible-grid",
    'data-section-filter="hoy"',
    'data-section-filter="fin-de-semana"',
    'data-section-filter="terminan-pronto"',
    'data-section-filter="gratis"',
    'data-section-filter="todos"',
    "data-category-filters",
    "data-filter-clear",
    "data-filter-summary",
    "data-total",
    "data-sources-section",
    "data-sources-grid",
    "data-sources-total",
)
for marker in required_index_markers:
    assert marker in index, f"missing UI marker: {marker}"

assert 'data-section-filter="proximos"' not in index
assert 'data-section-filter="talleres-cursos"' not in index
assert "Próximamente" not in index
assert "Talleres y cursos" not in index

assert 'event?.event_type === "program"' in app_js
assert 'event?.event_type === "flexible_offer"' in app_js
assert 'return "dated";' in app_js
assert 'groups = { dated: [], program: [], flexible: [] }' in app_js
assert "renderGroup(dom.datedGrid" in app_js
assert "renderGroup(dom.programGrid" in app_js
assert "renderGroup(dom.flexibleGrid" in app_js
assert 'total: document.querySelector("[data-total]")' in app_js
assert "dom.total.textContent" in app_js

assert 'timeZone: city.timezone' in app_js
assert 'activeSection = defaultSection()' in app_js
assert 'eventMatchesSection(event, "hoy")' in app_js
assert 'weekendBounds(today)' in app_js
assert 'sectionId === "terminan-pronto"' in app_js
assert 'collectCategoryCounts(allEvents)' in app_js
assert 'eventMatchesCategory(event, activeCategory)' in app_js

assert 'import "./card-experience.js";' in pwa_js
assert 'import "./card-image-fallback.js";' in pwa_js
assert 'import "./compact-top.js";' in pwa_js
assert 'import "./gijon-visual-reference.js";' in pwa_js
assert 'import "./lean-filters.js";' in pwa_js
assert 'dataset: "../agenda_web.json"' in card_js
assert 'dataset: "./data/gijon/agenda_web.json"' in card_js
assert 'event?.image?.url' in card_js
assert 'event-card-media' in card_js
assert 'event-facts' in card_js
assert 'priceLabel(event)' in card_js
assert 'locationLabel(event)' in card_js
assert '"No te lo pierdas"' in card_js
assert '"Termina pronto"' in card_js
assert 'event?.links?.registration' in card_js
assert 'card-action--primary' in card_js
assert 'event?.source_name' in card_js
assert 'event-card-source' in card_js
assert 'collectSources(allEvents)' in app_js
assert 'renderSources()' in app_js
assert 'source-card' in css
assert '.event-card-photo' in card_css
assert '.context-badge--featured' in card_css
assert '.event-card-actions' in card_css

assert 'activeCity() !== "valparaiso"' in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js
assert '../assets/categoria-exposiciones.jpg' in fallback_js
assert '../assets/categoria-cultura.jpg' in fallback_js
assert 'Imagen representativa de la categoría' in fallback_js

# Compact discovery: time/free controls and categories are kept separate.
assert '.discovery-heading' in compact_js
assert '.category-explorer-heading' in compact_js
assert '.quick-sections button' in compact_js
assert '.category-filters' in compact_js
assert 'flex-wrap: nowrap !important' in compact_js
assert '.section-heading p:not(.eyebrow)' in compact_js
assert '.agenda-heading' in compact_js
assert '.app-header' in compact_js
assert 'new Set(["hoy", "fin-de-semana", "terminan-pronto", "gratis", "todos"])' in lean_filters_js
assert 'data-section-filter="todos"' in lean_filters_js
assert "MutationObserver" in lean_filters_js

# Gijon keeps Open Data as the canonical source while exposing a separate,
# official visual browsing reference for users.
assert 'https://www.gijon.es/app/actividades/oferta' in gijon_visual_js
assert 'data-gijon-visual-reference' in gijon_visual_js
assert 'Explorar actividades en Gijón' in gijon_visual_js
assert 'grid.prepend(buildVisualReference())' in gijon_visual_js

assert "dataset público todavía no ha sido conectado" not in app_js
assert "No pudimos cargar la agenda" in app_js
assert '.quick-sections' in css
assert '.category-filters' in css
assert '.category-chip.active' in css
assert '@media(max-width:560px)' in css
assert '.event-grid,.compact-grid{grid-template-columns:1fr}' in css

assert 'const CACHE_VERSION = "v11";' in service_worker
assert "refreshOpenWindows" in service_worker
assert "client.navigate(client.url)" in service_worker
shell_block = service_worker.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
assert '"./card-experience.js"' in shell_block
assert '"./card-experience.css"' in shell_block
assert '"./card-image-fallback.js"' in shell_block
assert '"./compact-top.js"' in shell_block
assert '"./gijon-visual-reference.js"' in shell_block
assert '"./lean-filters.js"' in shell_block
assert '"../assets/categoria-exposiciones.jpg"' in shell_block

print("Multi-city lean time/free discovery, Gijon visual reference and partition tests: OK")
