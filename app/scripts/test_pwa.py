from __future__ import annotations

import json
import struct
from pathlib import Path

APP = Path("app")
manifest = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))
index = (APP / "index.html").read_text(encoding="utf-8")
pwa_js = (APP / "pwa.js").read_text(encoding="utf-8")
sw = (APP / "service-worker.js").read_text(encoding="utf-8")
fallback_js = (APP / "card-image-fallback.js").read_text(encoding="utf-8")
compact_top_js = (APP / "compact-top.js").read_text(encoding="utf-8")
gijon_visual_js = (APP / "gijon-visual-reference.js").read_text(encoding="utf-8")
lean_filters_js = (APP / "lean-filters.js").read_text(encoding="utf-8")
sources_toggle_js = (APP / "sources-toggle.js").read_text(encoding="utf-8")

assert manifest["start_url"] == "./"
assert manifest["scope"] == "./"
assert manifest["display"] == "standalone"
assert manifest["theme_color"]
assert manifest["background_color"]

icons = {icon["src"]: icon for icon in manifest["icons"]}
expected = {
    "./icons/icon-192.png": (192, 192, "any"),
    "./icons/icon-512.png": (512, 512, "any"),
    "./icons/icon-maskable-512.png": (512, 512, "maskable"),
}


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"not a PNG: {path}"
    assert data[12:16] == b"IHDR", f"missing IHDR: {path}"
    return struct.unpack(">II", data[16:24])


for src, (width, height, purpose) in expected.items():
    assert src in icons, f"manifest missing {src}"
    icon = icons[src]
    assert icon["sizes"] == f"{width}x{height}"
    assert purpose in icon.get("purpose", "").split()
    path = APP / src.removeprefix("./")
    assert path.exists(), f"icon file missing: {path}"
    assert png_size(path) == (width, height), f"wrong PNG dimensions: {path}"

assert '<link rel="manifest" href="./manifest.webmanifest">' in index
assert '<link rel="apple-touch-icon" href="./icons/icon-192.png">' in index
assert '<link rel="stylesheet" href="./city-header.css">' in index
assert '<script type="module" src="./pwa.js"></script>' in index
assert "data-install-app" in index
assert "data-app-version" in index

for marker in (
    'data-section-filter="hoy"',
    'data-section-filter="fin-de-semana"',
    'data-section-filter="terminan-pronto"',
    'data-section-filter="gratis"',
    'data-section-filter="todos"',
):
    assert marker in index
assert 'data-section-filter="proximos"' not in index
assert 'data-section-filter="talleres-cursos"' not in index

for module in (
    './card-experience.js',
    './card-image-fallback.js',
    './compact-top.js',
    './gijon-visual-reference.js',
    './lean-filters.js',
    './sources-toggle.js',
):
    assert f'import "{module}";' in pwa_js
assert 'const APP_VERSION = "PWA v11";' in pwa_js
assert 'navigator.serviceWorker.register("./service-worker.js"' in pwa_js
assert 'scope: "./"' in pwa_js
assert 'updateViaCache: "none"' in pwa_js

assert '.hero > h1' in compact_top_js
assert '.agenda-heading' in compact_top_js
assert 'display: none !important' in compact_top_js
assert '.category-filters' in compact_top_js

assert 'https://www.gijon.es/app/actividades/oferta' in gijon_visual_js
assert 'data-gijon-visual-reference' in gijon_visual_js

assert 'new Set(["hoy", "fin-de-semana", "terminan-pronto", "gratis", "todos"])' in lean_filters_js
assert 'data-section-filter="todos"' in lean_filters_js
assert 'attributeFilter: ["hidden"]' in lean_filters_js

assert 'data-sources-section' in sources_toggle_js
assert 'button.dataset.sourcesToggle' in sources_toggle_js
assert 'sources-user-open' in sources_toggle_js
assert 'aria-expanded' in sources_toggle_js
assert 'Fuentes' in sources_toggle_js

assert 'activeCity() !== "valparaiso"' in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js

assert 'const CACHE_VERSION = "v12"' in sw
assert "async function refreshOpenWindows" in sw
assert "await refreshOpenWindows()" in sw

shell_block = sw.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
for asset in (
    '"./"', '"./index.html"', '"./app.css"', '"./city-header.css"', '"./app.js"', '"./pwa.js"',
    '"./card-experience.js"', '"./card-experience.css"', '"./card-image-fallback.js"',
    '"./compact-top.js"', '"./gijon-visual-reference.js"', '"./lean-filters.js"',
    '"./sources-toggle.js"', '"./manifest.webmanifest"', '"./icons/icon.svg"',
    '"./icons/icon-192.png"', '"./icons/icon-512.png"', '"./icons/icon-maskable-512.png"',
    '"../assets/categoria-cine.jpg"', '"../assets/categoria-cultura.jpg"',
    '"../assets/categoria-deportes.jpg"', '"../assets/categoria-exposiciones.jpg"',
    '"../assets/categoria-gastronomia.jpg"', '"../assets/categoria-musica.jpg"',
    '"../assets/categoria-naturaleza.jpg"', '"../assets/categoria-talleres.jpg"',
    '"../assets/categoria-teatro.jpg"',
):
    assert asset in shell_block, f"shell precache missing {asset}"
assert "agenda_web.json" not in shell_block

assert 'new URL("../agenda_web.json", self.registration.scope).href' in sw
assert 'new URL("./data/gijon/agenda_web.json", self.registration.scope).href' in sw
assert "async function networkFirstDataset" in sw
assert 'fetch(request, { cache: "no-store" })' in sw
assert "offline_dataset_unavailable" in sw

print("PWA contract tests: OK")
