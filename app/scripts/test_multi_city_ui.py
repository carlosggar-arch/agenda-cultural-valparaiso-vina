from pathlib import Path

index = Path("app/index.html").read_text(encoding="utf-8")
app_js = Path("app/app.js").read_text(encoding="utf-8")
pwa_js = Path("app/pwa.js").read_text(encoding="utf-8")
css = Path("app/app.css").read_text(encoding="utf-8")
city_header_css = Path("app/city-header.css").read_text(encoding="utf-8")
header_redesign_css = Path("app/header-redesign.css").read_text(encoding="utf-8")
header_redesign_js = Path("app/header-redesign.js").read_text(encoding="utf-8")
card_js = Path("app/card-experience.js").read_text(encoding="utf-8")
card_css = Path("app/card-experience.css").read_text(encoding="utf-8")
fallback_js = Path("app/card-image-fallback.js").read_text(encoding="utf-8")
compact_js = Path("app/compact-top.js").read_text(encoding="utf-8")
gijon_visual_js = Path("app/gijon-visual-reference.js").read_text(encoding="utf-8")
lean_filters_js = Path("app/lean-filters.js").read_text(encoding="utf-8")
community_source_js = Path("app/community-source.js").read_text(encoding="utf-8")
source_form = Path("app/proponer-fuente.html").read_text(encoding="utf-8")
service_worker = Path("app/service-worker.js").read_text(encoding="utf-8")
vivamos_brand_js = Path("app/vivamos-brand.js").read_text(encoding="utf-8")

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
    "data-city-masthead",
    "masthead-valpo",
    "masthead-gijon",
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

# City preference contract: the static bootstrap seeds a safe default so app.js
# will not force the chooser on ordinary first visits, while explicit city URLs
# and subsequent manual switches remain persistent.
assert 'const STORAGE_KEY = "agenda-cultural-city";' in index
assert 'new Set(["valparaiso", "gijon"])' in index
assert 'URLSearchParams(window.location.search).get("city")' in index
assert 'supported.has(saved) ? saved : "valparaiso"' in index
assert 'localStorage.setItem(STORAGE_KEY, city)' in index
assert 'document.documentElement.dataset.city = city' in index
assert 'new MutationObserver(applyCityChrome)' in index
assert 'url.searchParams.set("city", city)' in index
assert '<h2 id="chooser-title">Cambiar ciudad</h2>' in index
assert 'document.documentElement.dataset.city = id' in app_js
assert 'dom.citySwitch.addEventListener("click", () => showChooser(false))' in app_js
assert 'else showChooser(true);' in app_js  # fallback only when storage is unavailable

# Legacy city identity remains available underneath the stronger hero layer.
assert 'html[data-city="valparaiso"] .masthead-valpo' in city_header_css
assert 'html[data-city="gijon"] .masthead-gijon' in city_header_css
assert '.gijon-wave' in city_header_css
assert '.gijon-mark' in city_header_css
assert '.masthead-valpo span:nth-child(8)' in city_header_css
assert '.brand img{width:72px;height:72px' in city_header_css

# The current hero keeps the city identity strong but removes the permanent
# search bar. Search remains available through a compact magnifier control and
# a floating field. Long city names must stay on one line.
assert 'import "./header-redesign.js";' in pwa_js
assert pwa_js.rfind('import "./header-redesign.js";') > pwa_js.rfind('import "./compact-top.js";')
assert 'header.dataset.headerRedesign = "hero-v3"' in header_redesign_js
assert 'actions.prepend(toggle)' in header_redesign_js
assert 'searchPopover.append(searchRow)' in header_redesign_js
assert 'toggle.setAttribute("aria-label", "Buscar actividades")' in header_redesign_js
assert 'requestAnimationFrame(() => input?.focus())' in header_redesign_js
assert 'bottom.append(searchRow)' not in header_redesign_js
assert 'bottom.append(actions)' in header_redesign_js
assert 'art.className = "header-art"' in header_redesign_js
assert 'min-height:218px!important' in header_redesign_css
assert 'position:relative!important' in header_redesign_css
assert '.header-city-title' in header_redesign_css
assert 'white-space:nowrap' in header_redesign_css
assert 'font-size:clamp(1.6rem,3.65vw,3.25rem)' in header_redesign_css
assert '.header-search-toggle' in header_redesign_css
assert '.header-search-popover' in header_redesign_css
assert '.header-search-popover[hidden]{display:none!important}' in header_redesign_css
assert './illustrations/valparaiso-header.svg' in header_redesign_css
assert './illustrations/gijon-header.svg' in header_redesign_css
assert Path("app/illustrations/valparaiso-header.svg").exists()
assert Path("app/illustrations/gijon-header.svg").exists()

assert 'import "./vivamos-brand.js";' in pwa_js
assert 'import "./card-experience.js";' in pwa_js
assert 'import "./card-image-fallback.js";' in pwa_js
assert 'import "./compact-top.js";' in pwa_js
assert 'import "./gijon-visual-reference.js";' in pwa_js
assert 'import "./lean-filters.js";' in pwa_js
assert 'import "./community-source.js";' in pwa_js
assert 'const BRAND_NAME = "¡Vivamos!";' in vivamos_brand_js
assert 'const BRAND_TAGLINE = "Descubre y vive lo que hay cerca de ti.";' in vivamos_brand_js
assert 'import { BRAND_TAGLINE } from "./vivamos-brand.js";' in header_redesign_js
assert 'const TAGLINE = BRAND_TAGLINE;' in header_redesign_js
assert 'Cultura, panoramas y experiencias para disfrutar cerca de ti.' not in header_redesign_js
assert '<span>Descubre y vive lo que hay cerca de ti.</span>' in index
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

assert '.discovery-heading' in compact_js
assert '.category-explorer-heading' in compact_js
assert '.quick-sections button' in compact_js
assert '.category-filters' in compact_js
# Filter visibility contract: options must wrap into an adaptive grid rather
# than being hidden behind a horizontal carousel.
assert 'display: grid !important' in compact_js
assert 'grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)) !important' in compact_js
assert 'grid-template-columns: repeat(auto-fit, minmax(138px, 1fr)) !important' in compact_js
assert 'grid-template-columns: repeat(2, minmax(0, 1fr)) !important' in compact_js
assert 'overflow: visible !important' in compact_js
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

assert 'const CACHE_VERSION = "v21";' in service_worker
assert "refreshOpenWindows" in service_worker
assert "client.navigate(client.url)" in service_worker
shell_block = service_worker.split("const SHELL_ASSETS = [", 1)[1].split("];", 1)[0]
assert '"./city-header.css"' in shell_block
assert '"./header-redesign.css"' in shell_block
assert '"./vivamos-brand.js"' in shell_block
assert '"./header-redesign.js"' in shell_block
assert '"./card-experience.js"' in shell_block
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
assert '"../assets/categoria-exposiciones.jpg"' in shell_block

print("Multi-city persistent header, compact search hero, visible filter grid and Vivamos brand tests: OK")
