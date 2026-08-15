from pathlib import Path

# Dependency-free static contract for the preview shell. The goal is to catch
# accidental regressions in the three-way content partition before the
# scheduled Gijón workflow updates the branch.
index = Path("app/index.html").read_text(encoding="utf-8")
app_js = Path("app/app.js").read_text(encoding="utf-8")
css = Path("app/app.css").read_text(encoding="utf-8")

required_index_markers = (
    "data-dated-section",
    "data-dated-grid",
    "data-program-section",
    "data-program-grid",
    "data-flexible-section",
    "data-flexible-grid",
)
for marker in required_index_markers:
    assert marker in index, f"missing UI marker: {marker}"

assert 'event?.event_type === "program"' in app_js
assert 'event?.event_type === "flexible_offer"' in app_js
assert 'return "dated";' in app_js
assert 'groups = { dated: [], program: [], flexible: [] }' in app_js
assert "renderGroup(dom.programGrid" in app_js
assert "renderGroup(dom.flexibleGrid" in app_js
assert "dataset público todavía no ha sido conectado" not in app_js
assert "No pudimos cargar la agenda" in app_js
assert "@media(max-width:560px)" in css
assert ".event-grid,.compact-grid{grid-template-columns:1fr}" in css

print("Multi-city UI partition tests: OK")
