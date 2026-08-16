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
assert "min-height: 158px !important" in density
assert "width: 62% !important" in density
assert "opacity: .7 !important" in density

print("Contextual filter and compact density tests: OK")
