from pathlib import Path

APP = Path("app")
index = (APP / "index.html").read_text(encoding="utf-8")
app_js = (APP / "app.js").read_text(encoding="utf-8")
pwa = (APP / "pwa.js").read_text(encoding="utf-8")
sw = (APP / "service-worker.js").read_text(encoding="utf-8")
css = (APP / "visual-identity.css").read_text(encoding="utf-8")

assert '<link rel="stylesheet" href="./visual-identity.css">' in index
assert 'document.documentElement.dataset.city = id;' in app_js
assert 'card.dataset.category = eventCategoryId(event);' in app_js
assert 'const APP_VERSION = "PWA v7";' in pwa
assert 'const CACHE_VERSION = "v7"' in sw
assert '"./visual-identity.css"' in sw.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
assert 'html[data-city="valparaiso"]' in css
assert 'html[data-city="gijon"]' in css
for category in ("musica", "cine", "teatro", "exposiciones", "museos", "cursos-talleres"):
    assert f'data-category="{category}"' in css
    assert f'data-category-filter="{category}"' in css
assert '.sources-section' in css
assert 'prefers-reduced-motion' in css
print("Visual identity contract: OK")
