from pathlib import Path

DETAIL = Path("app/event-detail.js").read_text(encoding="utf-8")

assert "function isGijonOpenDataEvent" in DETAIL
assert '"Datos oficiales"' in DETAIL
assert '"Información oficial disponible"' in DETAIL
assert "Open Data del Ayuntamiento de Gijón/Xixón" in DETAIL
assert "Para evitar páginas municipales individuales que no muestran contenido" in DETAIL
assert '"Open Data oficial ↗"' in DETAIL
assert '"Página municipal ↗"' not in DETAIL
assert '"Fuente oficial ↗"' in DETAIL, "non-Gijon source behaviour must remain available"
assert "function permanentEventUrl(event)" in DETAIL
assert '"Ficha permanente →"' not in DETAIL
assert '"Añadir al calendario"' in DETAIL
assert '"Compartir"' in DETAIL
assert '"Copiar enlace"' not in DETAIL

print("Gijón official Open Data event-detail contract: OK")
