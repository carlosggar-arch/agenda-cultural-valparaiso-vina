from pathlib import Path

DETAIL = Path("app/event-detail.js").read_text(encoding="utf-8")

assert "function isGijonOpenDataEvent" in DETAIL
assert '"Datos oficiales"' in DETAIL
assert '"Información oficial disponible"' in DETAIL
assert "Open Data del Ayuntamiento de Gijón/Xixón" in DETAIL
assert "La página municipal individual puede aparecer vacía" in DETAIL
assert '"Open Data oficial ↗"' in DETAIL
assert '"Página municipal ↗"' in DETAIL
assert '"Fuente oficial ↗"' in DETAIL, "non-Gijon source behaviour must remain available"
assert DETAIL.index('"Open Data oficial ↗"') < DETAIL.index('"Página municipal ↗"')

print("Gijón official Open Data event-detail contract: OK")
