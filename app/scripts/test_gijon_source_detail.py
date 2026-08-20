import copy
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_event_pages as PERMANENT  # noqa: E402
import stage31_site_generator as STAGE31  # noqa: E402

# This contract is part of the existing multi-city pre-release gate.
DETAIL = (ROOT / "app/event-detail.js").read_text(encoding="utf-8")
DATASET = json.loads((ROOT / "app/data/gijon/agenda_web.json").read_text(encoding="utf-8"))

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

# Static permanent pages must apply the same editorial rule before JavaScript runs.
sample = next(
    event
    for event in DATASET.get("events", [])
    if event.get("title") == "El cine del centro"
)
links = sample.get("links") or {}
municipal = links.get("municipal_page")
open_data = sample.get("source_url") or links.get("source")
assert municipal and not is_open_data(municipal)
assert open_data and is_open_data(open_data)

stamp = PERMANENT.generated_at(DATASET)
event_url = PERMANENT.page_url("gijon", sample)
page, ics = PERMANENT.render_page(
    "gijon",
    PERMANENT.CITY_CONFIG["gijon"],
    sample,
    [],
    stamp,
)
assert municipal in page
assert "Fuente corroborante ↗" in page
assert "<dt>Fuente mostrada</dt>" in page
assert "Ayuntamiento de Gijón/Xixón — ficha específica del evento" in page
assert "opendata.gijon.es" not in page
assert ics is not None, "Representative Gijón Open Data event should produce ICS"
assert municipal in ics
assert "opendata.gijon.es" not in ics

base_ld = PERMANENT.structured_event("gijon", sample, event_url)
assert base_ld.get("sameAs") == municipal
assert "opendata.gijon.es" not in json.dumps(base_ld, ensure_ascii=False)

stage_ld = STAGE31.structured_page_document("gijon", sample, event_url)
stage_ld_text = json.dumps(stage_ld, ensure_ascii=False)
assert municipal in stage_ld_text
assert "opendata.gijon.es" not in stage_ld_text

stage_page, stage_ics = STAGE31.enhance_event_page(
    "gijon",
    PERMANENT.CITY_CONFIG["gijon"],
    sample,
    [],
    stamp,
)
assert municipal in stage_page
assert "opendata.gijon.es" not in stage_page
assert stage_ics is not None and municipal in stage_ics
assert "opendata.gijon.es" not in stage_ics

# Open Data remains an explicit last resort when a corroborating page is absent.
fallback = copy.deepcopy(sample)
fallback_links = fallback.get("links") or {}
fallback_links.pop("municipal_page", None)
fallback_links.pop("official", None)
fallback["links"] = fallback_links
fallback_page, fallback_ics = PERMANENT.render_page(
    "gijon",
    PERMANENT.CITY_CONFIG["gijon"],
    fallback,
    [],
    stamp,
)
assert "Open Data — último recurso ↗" in fallback_page
assert "opendata.gijon.es" in fallback_page
assert fallback_ics is not None and "opendata.gijon.es" in fallback_ics

print(f"Gijón corroborating-source event-detail contract: OK ({checked} Open Data events checked)")
print("Gijón static HTML/JSON-LD/ICS corroborating-source contract: OK")
