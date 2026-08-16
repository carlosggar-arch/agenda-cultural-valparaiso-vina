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
card_experience_js = (APP / "card-experience.js").read_text(encoding="utf-8")
schedule_display_js = (APP / "schedule-display.js").read_text(encoding="utf-8")
event_detail_js = (APP / "event-detail.js").read_text(encoding="utf-8")
media_css = Path("assets/event-media-layout.css").read_text(encoding="utf-8")
schedule_module = Path("assets/event-schedule-display.mjs").read_text(encoding="utf-8")
compact_top_js = (APP / "compact-top.js").read_text(encoding="utf-8")
gijon_visual_js = (APP / "gijon-visual-reference.js").read_text(encoding="utf-8")
lean_filters_js = (APP / "lean-filters.js").read_text(encoding="utf-8")
sources_toggle_js = (APP / "sources-toggle.js").read_text(encoding="utf-8")
community_source_js = (APP / "community-source.js").read_text(encoding="utf-8")
source_form = (APP / "proponer-fuente.html").read_text(encoding="utf-8")
vivamos_brand_js = (APP / "vivamos-brand.js").read_text(encoding="utf-8")
header_redesign_js = (APP / "header-redesign.js").read_text(encoding="utf-8")
header_redesign_css = (APP / "header-redesign.css").read_text(encoding="utf-8")
source_form_js = (APP / "proponer-fuente.js").read_text(encoding="utf-8")

assert manifest["start_url"] == "./"
assert manifest["scope"] == "./"
assert manifest["display"] == "standalone"
assert manifest["theme_color"]
assert manifest["background_color"]
assert manifest["name"] == "¡Vivamos!"
assert manifest["short_name"] == "¡Vivamos!"
assert "Descubre y vive lo que hay cerca de ti" in manifest["description"]

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
assert '<meta name="description" content="¡Vivamos!: Descubre y vive lo que hay cerca de ti.">' in index
assert '<strong>¡Vivamos!</strong>' in index
assert '<span>Descubre y vive lo que hay cerca de ti.</span>' in index

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
    './vivamos-brand.js',
    './card-experience.js',
    './schedule-display.js',
    './card-image-fallback.js',
    './compact-top.js',
    './gijon-visual-reference.js',
    './lean-filters.js',
    './sources-toggle.js',
    './community-source.js',
    './header-redesign.js',
):
    assert f'import "{module}";' in pwa_js
assert pwa_js.rfind('import "./header-redesign.js";') > pwa_js.rfind('import "./compact-top.js";')
assert 'const APP_VERSION = "PWA v23";' in pwa_js
assert 'navigator.serviceWorker.register("./service-worker.js"' in pwa_js
assert 'scope: "./"' in pwa_js
assert 'updateViaCache: "none"' in pwa_js

assert 'MEDIA_STYLESHEET = "../assets/event-media-layout.css?v=20260816"' in card_experience_js
assert 'className = "card-meta-right"' in card_experience_js
assert 'card-day-badge' in card_experience_js
assert 'looksLikeGenericSchedule(event)' in card_experience_js
assert 'media.classList.add("has-relevant-image")' in card_experience_js
assert 'image.dataset.eventImage = "relevant"' in card_experience_js
assert 'imageRelevant: Boolean(relevantImageUrl(event))' in card_experience_js
assert 'presentation?.imageRelevant === false' in event_detail_js
assert 'media.classList.add("has-relevant-image")' in event_detail_js
assert 'object-fit: contain !important' in media_css
assert '.card-day-badge' in media_css
assert '.event-media-fallback' in media_css
assert 'filter: blur(18px)' in media_css
assert '.card-media > button' in media_css
assert '.event-card-media > button' in media_css
assert 'display: none !important' in media_css

assert 'from "../assets/event-schedule-display.mjs"' in schedule_display_js
assert 'formatSchedule(event.schedule, activeConfig)' in schedule_display_js
assert 'Fecha y horario' in schedule_display_js
assert 'stripMediaControls' in schedule_display_js
assert 'export function formatSchedule' in schedule_module
assert 'schedule?.opening_time' in schedule_module
assert 'schedule?.opening_hours' in schedule_module
assert 'Cerrado hoy' in schedule_module
assert 'export function compactScheduleDayLabel' in schedule_module

assert 'import "./vivamos-brand.js";' in source_form_js
assert 'const BRAND_NAME = "¡Vivamos!";' in vivamos_brand_js
assert 'const BRAND_TAGLINE = "Descubre y vive lo que hay cerca de ti.";' in vivamos_brand_js

assert 'import { BRAND_TAGLINE } from "./vivamos-brand.js";' in header_redesign_js
assert 'const TAGLINE = BRAND_TAGLINE;' in header_redesign_js
assert 'Cultura, panoramas y experiencias para disfrutar cerca de ti.' not in header_redesign_js
assert 'header.dataset.headerRedesign = "hero-v3"' in header_redesign_js
assert 'actions.prepend(toggle)' in header_redesign_js
assert 'searchPopover.append(searchRow)' in header_redesign_js
assert 'toggle.setAttribute("aria-label", "Buscar actividades")' in header_redesign_js
assert 'requestAnimationFrame(() => input?.focus())' in header_redesign_js
assert 'bottom.append(searchRow)' not in header_redesign_js
assert 'bottom.append(actions)' in header_redesign_js
assert 'art.className = "header-art"' in header_redesign_js
assert '.app-header{' in header_redesign_css
assert 'min-height:218px!important' in header_redesign_css
assert 'position:relative!important' in header_redesign_css
assert 'white-space:nowrap' in header_redesign_css
assert 'font-size:clamp(1.6rem,3.65vw,3.25rem)' in header_redesign_css
assert '.header-search-toggle' in header_redesign_css
assert '.header-search-popover' in header_redesign_css
assert '.header-search-popover[hidden]{display:none!important}' in header_redesign_css
assert './illustrations/valparaiso-header.svg' in header_redesign_css
assert './illustrations/gijon-header.svg' in header_redesign_css
assert (APP / "illustrations" / "valparaiso-header.svg").exists()
assert (APP / "illustrations" / "gijon-header.svg").exists()

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
assert 'dataset?.sources' in sources_toggle_js
assert 'Fuente incorporada · sin eventos importados en esta ejecución' in sources_toggle_js
assert 'Fuentes${count ? ` · ${count}` : ""}' in sources_toggle_js

assert 'data-source-proposal-cta' in community_source_js
assert 'proponer-fuente.html' in community_source_js
assert 'data-community-source-form' in source_form
assert 'cf-turnstile' in source_form

assert 'activeCity() !== "valparaiso"' in fallback_js
assert 'image.dataset.imageKind = "category-fallback"' in fallback_js

assert 'const CACHE_VERSION = "v23"' in sw
assert "async function refreshOpenWindows" in sw
assert "await refreshOpenWindows()" in sw

shell_block = sw.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
for asset in (
    '"./"', '"./index.html"', '"./app.css"', '"./city-header.css"', '"./header-redesign.css"',
    '"./app.js"', '"./pwa.js"', '"./vivamos-brand.js"', '"./header-redesign.js"',
    '"./card-experience.js"', '"./schedule-display.js"', '"./card-experience.css"', '"./card-image-fallback.js"',
    '"./compact-top.js"', '"./gijon-visual-reference.js"', '"./lean-filters.js"',
    '"./sources-toggle.js"', '"./community-source.js"', '"./community-source.css"',
    '"./proponer-fuente.html"', '"./proponer-fuente.js"', '"./manifest.webmanifest"', '"./icons/icon.svg"',
    '"./icons/icon-192.png"', '"./icons/icon-512.png"', '"./icons/icon-maskable-512.png"',
    '"./illustrations/valparaiso-header.svg"', '"./illustrations/gijon-header.svg"',
    '"../assets/event-media-layout.css"', '"../assets/event-schedule-display.mjs"',
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
