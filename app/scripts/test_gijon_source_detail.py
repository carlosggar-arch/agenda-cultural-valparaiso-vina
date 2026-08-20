from pathlib import Path

DETAIL = Path("app/event-detail.js").read_text(encoding="utf-8")

assert "function isGijonOpenDataEvent" in DETAIL
assert "function isGijonOpenDataUrl" in DETAIL
assert "function gijonCorroboratingSource" in DETAIL
assert '"Fuente mostrada"' in DETAIL
assert '"Verificación de la información"' in DETAIL
assert "Open Data del Ayuntamiento de Gijón/Xixón" in DETAIL
assert "la fuente que se muestra al público es una ficha específica" in DETAIL
assert '"Fuente corroborante ↗"' in DETAIL
assert '"Open Data — último recurso ↗"' in DETAIL
assert '"Fuente oficial ↗"' in DETAIL, "non-Gijon source behaviour must remain available"
assert "function permanentEventUrl(event)" in DETAIL
assert '"Ficha permanente →"' not in DETAIL
assert '"Añadir al calendario"' in DETAIL
assert '"Compartir"' in DETAIL
assert '"Copiar enlace"' not in DETAIL

print("Gijón corroborating-source event-detail contract: OK")
