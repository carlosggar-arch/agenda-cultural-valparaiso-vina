from pathlib import Path

# Dependency-free static contract for the multi-city shell. It protects the
# three-way editorial partition plus the discovery/navigation and card layers
# shared by Valparaiso/Vina and Gijon.
index = Path("app/index.html").read_text(encoding="utf-8")
app_js = Path("app/app.js").read_text(encoding="utf-8")
pwa_js = Path("app/pwa.js").read_text(encoding="utf-8")
css = Path("app/app.css").read_text(encoding="utf-8")
card_js = Path("app/card-experience.js").read_text(encoding="utf-8")
card_css = Path("app/card-experience.css").read_text(encoding="utf-8")
fallback_js = Path("app/card-image-fallback.js").read_text(encoding="utf-8")
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
    'data-section-filter="proximos"',
    'data-section-filter="terminan-pronto"',
    'data-section-filter="gratis"',
    'data-section-filter="talleres-cursos"',
    "data-category-filters",
    "data-filter-clear",
    "data-filter-summary",
    "data-total",
)
for marker in required_index_markers:
    assert marker in index, f"missing UI marker: {marker}"

assert 'event?.event_type === "program"' in app_js
assert 'event?.event_type === "flexible_offer"' in app_js
assert 'return "dated";' in app_js
assert 'groups = { dated: [], program: [], flexible: [] }' in app_js
assert "renderGroup(dom.datedGrid" in app_js
assert "renderGroup(dom.programGrid" in app_js
assert "renderGroup(dom.flexibleGrid" in app_js
assert 'total: document.querySelector("[data-total]")' in app_js
assert "dom.total.textContent" in app_js

# Discovery must be city-timezone aware and data-driven, not hard-coded to Chile.
assert 'timeZone: city.timezone' in app_js
assert 'activeSection = defaultSection()' in app_js
assert 'eventMatchesSection(event, "hoy")' in app_js
assert 'weekendBounds(today)' in app_js
assert 'sectionId === "terminan-pronto"' in app_js
assert 'collectCategoryCounts(allEvents)' in app_js
assert 'eventMatchesCategory(event, activeCategory)' in app_js

# Rich cards are a presentation layer only: they consume the same selected-city
# public dataset and do not duplicate source extraction or editorial ingestion.
assert 'import "./card-experience.js";' in pwa_js
assert 'import "./card-image-fallback.js";' in pwa_js
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
assert '.event-card-photo' in card_css
assert '.context-badge--featured' in card_css
assert '.event-card-actions' in card_css

# Valparaiso/Vina must use the legacy category-photo library only when a real
# event image is missing; Gijon is deliberately excluded from this fallback.
assert 'activeCity() !== "valparaiso"' in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js
assert '../assets/categoria-exposiciones.jpg' in fallback_js
assert '../assets/categoria-cultura.jpg' in fallback_js
assert 'Imagen representativa de la categoría' in fallback_js

assert "dataset público todavía no ha sido conectado" not in app_js
assert "No pudimos cargar la agenda" in app_js
assert '.quick-sections' in css
assert '.category-filters' in css
assert '.category-chip.active' in css
assert '@media(max-width:560px)' in css
assert '.event-grid,.compact-grid{grid-template-columns:1fr}' in css

# The installed-shell recovery remains active and the card/fallback resources
# are part of the offline shell so presentation survives an offline reopen.
assert 'const CACHE_VERSION = "v5";' in service_worker
assert "refreshOpenWindows" in service_worker
assert "client.navigate(client.url)" in service_worker
shell_block = service_worker.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
assert '"./card-experience.js"' in shell_block
assert '"./card-experience.css"' in shell_block
assert '"./card-image-fallback.js"' in shell_block
assert '"../assets/categoria-exposiciones.jpg"' in shell_block

print("Multi-city discovery, rich-card render, Valpo image fallback and partition tests: OK")
