from pathlib import Path

source = Path("app/contextual-filters.js").read_text(encoding="utf-8")
density = Path("app/density-polish.js").read_text(encoding="utf-8")
gijon_svg = Path("app/illustrations/gijon-header.svg").read_text(encoding="utf-8")

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
assert "width: 62px !important" in density
assert "font-size: 1.52rem !important" in density
assert "font-size: .72rem !important" in density
assert "font-size: clamp(1.55rem, 3.35vw, 3rem) !important" in density
assert "background-position: right 58% !important" in density
assert '@media (min-width: 701px)' in density
assert 'html[data-city="gijon"] .app-header .header-art' in density
assert "width: 62% !important" in density
assert "opacity: .74 !important" in density
assert "background-position: right 41% !important" in density
assert "#000 18%" in density
assert "font-size: 1.18rem !important" in density
assert "font-size: .62rem !important" in density
assert "grid-template-columns: repeat(3, minmax(0, 1fr)) !important" in density

assert 'id="gijon-boat"' in gijon_svg
assert 'scale(1.45)' in gijon_svg
assert 'opacity="0.96"' in gijon_svg

print("Contextual filter and compact density tests: OK")
