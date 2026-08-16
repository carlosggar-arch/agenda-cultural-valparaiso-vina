from pathlib import Path

source = Path("app/contextual-filters.js").read_text(encoding="utf-8")

assert "const nextCountValue = counts.get(id) || 0;" in source
assert "button.hidden = nextCountValue === 0;" in source
assert "button.hidden = false;" not in source.split("function patchCategoryChips()", 1)[1].split("function patchCityControl()", 1)[0]
assert "searchInput?.addEventListener(\"input\", queueUpdate);" in source
assert "sectionFilters?.addEventListener(\"click\", queueUpdate);" in source

print("Contextual category visibility tests: OK")
