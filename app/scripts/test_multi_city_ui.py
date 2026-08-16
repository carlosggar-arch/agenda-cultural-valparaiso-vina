from pathlib import Path

# Dependency-free static contract for the multi-city shell. It protects the
# three-way editorial partition plus the discovery/navigation layer shared by
# Valparaiso/Vina and Gijon.
index = Path("app/index.html").read_text(encoding="utf-8")
app_js = Path("app/app.js").read_text(encoding="utf-8")
css = Path("app/app.css").read_text(encoding="utf-8")
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

assert "dataset público todavía no ha sido conectado" not in app_js
assert "No pudimos cargar la agenda" in app_js
assert '.quick-sections' in css
assert '.category-filters' in css
assert '.category-chip.active' in css
assert '@media(max-width:560px)' in css
assert '.event-grid,.compact-grid{grid-template-columns:1fr}' in css

# A rendering hotfix must invalidate the previous installed shell cache so a
# standalone PWA does not keep serving the broken UI contract.
assert 'const CACHE_VERSION = "v3";' in service_worker

print("Multi-city discovery, render and partition tests: OK")
