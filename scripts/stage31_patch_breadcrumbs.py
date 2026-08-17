from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "stage31_site_generator.py"
text = path.read_text(encoding="utf-8")

if "def structured_page_document(" not in text:
    anchor = "\ndef enhance_event_page(\n"
    if anchor not in text:
        raise SystemExit("EVENT_HELPER_ANCHOR_MISSING")
    helper = '''\n\ndef breadcrumb_schema(city_id: str, event: dict[str, Any], event_url: str) -> dict[str, Any]:
    title = str(event.get("title") or "Actividad cultural").strip()
    if city_id == "gijon":
        items = [
            {"@type": "ListItem", "position": 1, "name": "¡Vivamos! · Agenda Cultural", "item": f"{SITE_BASE}/"},
            {"@type": "ListItem", "position": 2, "name": "Agenda Cultural Gijón / Xixón", "item": CITY_SEO[city_id]["canonical"]},
            {"@type": "ListItem", "position": 3, "name": title, "item": event_url},
        ]
    else:
        items = [
            {"@type": "ListItem", "position": 1, "name": "Agenda Cultural Valparaíso / Viña del Mar", "item": CITY_SEO[city_id]["canonical"]},
            {"@type": "ListItem", "position": 2, "name": title, "item": event_url},
        ]
    return {"@type": "BreadcrumbList", "itemListElement": items}


def structured_page_document(city_id: str, event: dict[str, Any], event_url: str) -> dict[str, Any]:
    primary = dict(structured_document(city_id, event, event_url))
    primary.pop("@context", None)
    return {"@context": "https://schema.org", "@graph": [primary, breadcrumb_schema(city_id, event, event_url)]}
'''
    text = text.replace(anchor, helper + anchor, 1)

old = "    structured = _json_ld(structured_document(city_id, event, event_url))"
new = "    structured = _json_ld(structured_page_document(city_id, event, event_url))"
if new not in text:
    if old not in text:
        raise SystemExit("EVENT_JSONLD_ANCHOR_MISSING")
    text = text.replace(old, new, 1)

if "landing_primary = dict(ld)" not in text:
    old = '''    if image:\n        ld["image"] = image\n    og_image ='''
    new = '''    if image:\n        ld["image"] = image\n    landing_primary = dict(ld)\n    landing_primary.pop("@context", None)\n    ld = {\n        "@context": "https://schema.org",\n        "@graph": [\n            landing_primary,\n            {"@type": "BreadcrumbList", "itemListElement": [\n                {"@type": "ListItem", "position": 1, "name": "¡Vivamos! · Agenda Cultural", "item": f"{SITE_BASE}/"},\n                {"@type": "ListItem", "position": 2, "name": "Agenda Cultural Gijón / Xixón", "item": canonical},\n            ]},\n        ],\n    }\n    og_image ='''
    if old not in text:
        raise SystemExit("GIJON_JSONLD_ANCHOR_MISSING")
    text = text.replace(old, new, 1)

old = 'for required in ("Agenda Cultural de Gijón / Xixón", "application/ld+json", \'rel="canonical"\', \'class="skip-link"\', "ItemList"):'
new = 'for required in ("Agenda Cultural de Gijón / Xixón", "application/ld+json", \'rel="canonical"\', \'class="skip-link"\', "ItemList", "BreadcrumbList"):'
if new not in text:
    if old not in text:
        raise SystemExit("GIJON_VALIDATION_ANCHOR_MISSING")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("STAGE31_BREADCRUMB_PATCH_OK")
