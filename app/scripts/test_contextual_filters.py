from pathlib import Path

source = Path("app/contextual-filters.js").read_text(encoding="utf-8")
density = Path("app/density-polish.js").read_text(encoding="utf-8")

assert "const nextCountValue = counts.get(id) || 0;" in source
assert "button.hidden = nextCountValue === 0;" in source
assert "button.hidden = false;" not in source.split("function patchCategoryChips()", 1)[1].split("function patchCityControl()", 1)[0]
assert "searchInput?.addEventListener(\"input\", queueUpdate);" in source
assert "sectionFilters?.addEventListener(\"click\", queueUpdate);" in source

assert "function enforceQuickFilterVisibility()" in density
assert 'id !== "todos" && count === 0' in density
assert '.quick-sections [data-section-filter][hidden]' in density
assert 'container.querySelector(\'[data-section-filter="todos"]\')' in density
assert "white-space: nowrap !important" in density
assert "min-height: 0 !important" in density
assert "width: 58px !important" in density
assert "font-size: 1.32rem !important" in density
assert "font-size: clamp(1.55rem, 3.35vw, 3rem) !important" in density
assert "background-position: right 58% !important" in density
assert '@media (min-width: 701px)' in density
assert 'html[data-city="gijon"] .app-header .header-art' in density
assert "width: 60% !important" in density
assert "background-position: right 56% !important" in density
assert "#000 22%" in density
assert "grid-template-columns: repeat(3, minmax(0, 1fr)) !important" in density

print("Contextual filter and compact density tests: OK")
