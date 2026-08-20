from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"

index = (APP / "index.html").read_text(encoding="utf-8")
combined = (APP / "combined-filters.js").read_text(encoding="utf-8")
bootstrap = (APP / "combined-filters-bootstrap.js").read_text(encoding="utf-8")
polish = (APP / "combined-filters-polish.js").read_text(encoding="utf-8")
compact = (APP / "compact-top.css").read_text(encoding="utf-8")
compact_js = (APP / "compact-top.js").read_text(encoding="utf-8")
density = (APP / "density-polish.js").read_text(encoding="utf-8")
sources_toggle = (APP / "sources-toggle.js").read_text(encoding="utf-8")
pwa = (APP / "pwa.js").read_text(encoding="utf-8")
service_worker = (APP / "service-worker.js").read_text(encoding="utf-8")
gijon_svg = (APP / "illustrations/gijon-header.svg").read_text(encoding="utf-8")

assert 'data-combined-when' in index
assert 'data-combined-area' in index
assert 'data-combined-category-filters' in index
assert 'data-filter-value="manana"' in index
assert 'data-filter-value="7-dias"' in index
assert 'data-filter-value="personalizado"' in index
assert 'data-date-from' in index
assert 'data-date-to' in index
assert 'data-header-search-toggle' in index
assert 'data-header-search-popover' in index

assert 'const WHEN_VALUES = new Set(["todos", "hoy", "manana", "fin-de-semana", "7-dias", "terminan-pronto", "personalizado"]);' in combined
assert 'selectedWhen === "manana"' in combined
assert 'selectedWhen === "7-dias"' in combined
assert 'selectedWhen === "personalizado"' in combined
assert 'customFrom' in combined
assert 'customTo' in combined
assert 'URLSearchParams' in combined
assert 'url.searchParams.set("when", state.when)' in combined
assert 'url.searchParams.set("from", state.customFrom)' in combined
assert 'url.searchParams.set("to", state.customTo)' in combined
assert 'data-combined-count' in index
assert 'aria-pressed' in index

assert 'new CombinedFilterController' in bootstrap
assert 'data-combined-filters-ready' in bootstrap
assert 'data-combined-filter-panel' in polish
assert 'data-filter-summary' in polish
assert 'data-filter-clear' in polish

assert '.filter-workbench {' in compact
assert 'padding: 0 !important;' in compact
assert 'border: 0 !important;' in compact
assert 'background: transparent !important;' in compact
assert '.filter-workbench::before {' in compact
assert 'url("../assets/mosaic-top.png")' in compact
assert '.filter-group {' in compact
assert 'padding: .24rem 0 !important;' in compact
assert '[data-combined-when] {' in compact
assert 'padding-top: 1.55rem !important;' in compact
assert '[data-combined-when]::before {' in compact
assert 'content: "Cuándo";' in compact
assert '.filter-choice {' in compact
assert 'padding: .32rem .46rem !important;' in compact
assert '.category-filters {' in compact
assert 'minmax(116px, 1fr)' in compact
assert '@media (max-width: 560px)' in compact
assert 'flex-wrap: nowrap !important;' in compact
assert 'document.createElement("style")' not in compact_js
assert 'style.textContent' not in compact_js

assert "function enforceQuickFilterVisibility()" in density
assert 'id !== "todos" && count === 0' in density
assert '.quick-sections [data-section-filter][hidden]' in density
assert 'html[data-city="gijon"] .app-header .header-art' in density
assert 'id="gijon-boat"' in gijon_svg
assert 'scale(1.45)' in gijon_svg

assert "function sourceDiagnosticText(source)" in sources_toggle
assert "reviewed_items" in sources_toggle
assert "source_diagnostics" in sources_toggle
assert "canonical_source_id" in sources_toggle
assert "eventCountsBySourceId" in sources_toggle
assert "runtimeById" in sources_toggle
assert "DIAGNOSTIC_SOURCE_META" not in sources_toggle

assert 'globalThis.__VIVAMOS_RELEASE__' in pwa
assert 'const APP_VERSION = `PWA v${APP_RELEASE}`;' in pwa
assert 'service-worker.js?v=${APP_RELEASE}' in pwa
assert 'import "./combined-filters-polish.js";' in pwa
assert 'import "./plan-ahead.js";' in pwa
assert 'import "./favorites.js";' in pwa
assert 'importScripts("./release-version.js")' in service_worker
assert 'const CACHE_VERSION = `v${RELEASE}`;' in service_worker
assert '"./release-version.js"' in service_worker
assert '"./combined-filters.js"' in service_worker
assert '"./combined-filters.css"' in service_worker
assert '"./combined-filters-polish.js"' in service_worker
assert '"./compact-top.css"' in service_worker
assert '"./plan-ahead.js"' in service_worker
assert '"./favorites.js"' in service_worker
assert '"./mis-planes.html"' in service_worker
assert '"../assets/plan-ahead-core.mjs"' in service_worker
assert '"../assets/plan-ahead.css"' in service_worker
assert '"../assets/favorites-core.mjs"' in service_worker
assert '"../assets/favorites-view.mjs"' in service_worker
assert '"../assets/favorites-reminders.mjs"' in service_worker
assert '"../assets/favorites.css"' in service_worker

print("Contextual filters and canonical source diagnostics contract: OK")