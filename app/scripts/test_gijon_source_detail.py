import json
from pathlib import Path
from urllib.parse import urlparse

# This contract is part of the existing multi-city pre-release gate.
DETAIL = Path("app/event-detail.js").read_text(encoding="utf-8")
DATASET = json.loads(Path("app/data/gijon/agenda_web.json").read_text(encoding="utf-8"))

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


def host(value):
    try:
        return (urlparse(str(value or "")).hostname or "").lower()
    except Exception:
        return ""


def is_open_data(value):
    return host(value) == "opendata.gijon.es"


failures = []
checked = 0
for event in DATASET.get("events", []):
    links = event.get("links") or {}
    source = event.get("source_url") or links.get("source")
    source_name = str(event.get("source_name") or "").lower()
    if not (is_open_data(source) or ("open data" in source_name and "gij" in source_name)):
        continue
    checked += 1
    candidates = [links.get("municipal_page"), links.get("official")]
    if not any(url and not is_open_data(url) for url in candidates):
        failures.append(f"{event.get('id')}: {event.get('title')}")

assert not failures, "Open Data events without corroborating public source:\n- " + "\n- ".join(failures)
assert checked > 0, "Expected at least one Gijón Open Data event in the public dataset"

print(f"Gijón corroborating-source event-detail contract: OK ({checked} Open Data events checked)")
