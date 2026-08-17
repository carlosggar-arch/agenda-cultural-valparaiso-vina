from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "stage31_site_generator.py"
text = path.read_text(encoding="utf-8")

if "def root_structured_document(" not in text:
    anchor = "\ndef render_sitemap(event_entries: list[tuple[str, str | None]], city_lastmod: dict[str, str | None]) -> str:\n"
    if anchor not in text:
        raise SystemExit("ROOT_HELPER_ANCHOR_MISSING")
    helper = '''\n\ndef root_structured_document(payload: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = CITY_SEO["valparaiso"]["canonical"]
    org = f"{SITE_BASE}/#organization"
    website = f"{SITE_BASE}/#website"
    items = [{"@type": "ListItem", "position": n, "url": base.page_url("valparaiso", event), "name": str(event.get("title") or "Actividad cultural").strip()} for n, event in enumerate(events, 1)]
    collection = {
        "@type": "CollectionPage", "@id": f"{canonical}#agenda", "name": "Agenda Cultural Valparaíso / Viña del Mar", "url": canonical,
        "description": "Agenda cultural de Valparaíso y Viña del Mar con actividades revisadas desde fuentes verificables.", "inLanguage": "es-CL",
        "isPartOf": {"@id": website}, "publisher": {"@id": org},
        "spatialCoverage": [{"@type": "City", "name": "Valparaíso"}, {"@type": "City", "name": "Viña del Mar"}],
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(events), "itemListElement": items},
    }
    if payload.get("generated_at"):
        collection["dateModified"] = payload["generated_at"]
    return {"@context": "https://schema.org", "@graph": [
        {"@type": "Organization", "@id": org, "name": "¡Vivamos! · Agenda Cultural", "url": canonical},
        {"@type": "WebSite", "@id": website, "name": "¡Vivamos! · Agenda Cultural", "url": canonical, "inLanguage": "es-CL", "publisher": {"@id": org}},
        collection,
    ]}


def render_root_landing(payload: dict[str, Any], events: list[dict[str, Any]]) -> str:
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    page = page.replace('<html lang="es">', '<html lang="es-CL">', 1)
    if 'name="robots"' not in page:
        page = page.replace('<meta name="viewport" content="width=device-width,initial-scale=1">', '<meta name="viewport" content="width=device-width,initial-scale=1">\\n  <meta name="robots" content="index,follow,max-image-preview:large">', 1)
    if 'assets/accessibility.css' not in page:
        page = page.replace('<link rel="stylesheet" href="./assets/agenda.css">', '<link rel="stylesheet" href="./assets/agenda.css">\\n  <link rel="stylesheet" href="./assets/accessibility.css?v=20260817-stage31">', 1)
    page = page.replace('<main id="contenido">', '<main id="contenido" tabindex="-1">', 1)
    if 'property="og:site_name"' not in page:
        page = page.replace('<meta property="og:type" content="website">', '<meta property="og:type" content="website">\\n  <meta property="og:site_name" content="¡Vivamos! · Agenda Cultural">', 1)
    image = f"{SITE_BASE}/assets/cerro-concepcion-valparaiso.jpg?v=20260729-corrected"
    if 'property="og:image"' not in page:
        page = page.replace(f'<meta property="og:url" content="{SITE_BASE}/">', f'<meta property="og:url" content="{SITE_BASE}/">\\n  <meta property="og:image" content="{image}">', 1)
    page = page.replace('<meta name="twitter:card" content="summary">', '<meta name="twitter:card" content="summary_large_image">', 1)
    if 'name="twitter:image"' not in page:
        page = page.replace('</head>', f'  <meta name="twitter:image" content="{image}">\\n</head>', 1)
    script = '<script id="stage31-root-jsonld" type="application/ld+json">' + _json_ld(root_structured_document(payload, events)) + '</script>'
    pattern = r'<script id="stage31-root-jsonld" type="application/ld\\+json">.*?</script>'
    page = re.sub(pattern, script, page, count=1, flags=re.S) if re.search(pattern, page, flags=re.S) else page.replace('</head>', f'  {script}\\n</head>', 1)
    return page
'''
    text = text.replace(anchor, helper + anchor, 1)

old = '    sitemap = render_sitemap(event_entries, city_lastmod)\n    if f"{SITE_BASE}/gijon/" not in sitemap or f"{SITE_BASE}/app/" in sitemap:'
new = '    root_landing = render_root_landing(city_payloads["valparaiso"], city_events["valparaiso"])\n    for required in (\'lang="es-CL"\', \'name="robots"\', \'assets/accessibility.css\', \'id="stage31-root-jsonld"\', "CollectionPage", "ItemList", \'main id="contenido" tabindex="-1"\'):\n        if required not in root_landing:\n            raise SystemExit(f"Valpo root landing page missing {required}")\n    app_index = (ROOT / "app" / "index.html").read_text(encoding="utf-8")\n    for required in (\'data-stage31-accessibility\', \'main id="contenido" tabindex="-1"\'):\n        if required not in app_index:\n            raise SystemExit(f"PWA accessibility shell missing {required}")\n\n    sitemap = render_sitemap(event_entries, city_lastmod)\n    if f"{SITE_BASE}/gijon/" not in sitemap or f"{SITE_BASE}/app/" in sitemap:'
if new not in text:
    if old not in text:
        raise SystemExit("ROOT_GENERATE_ANCHOR_MISSING")
    text = text.replace(old, new, 1)

old = '    if not check:\n        gijon_dir = ROOT / "gijon"'
new = '    if not check:\n        (ROOT / "index.html").write_text(root_landing, encoding="utf-8")\n        gijon_dir = ROOT / "gijon"'
if new not in text:
    if old not in text:
        raise SystemExit("ROOT_WRITE_ANCHOR_MISSING")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("STAGE31_ROOT_PATCH_OK")
