from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"STAGE32_ANCHOR_MISSING:{path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


patch(
    "app/pwa.js",
    'import "./stage31-accessibility-seo.js";\n',
    'import "./stage31-accessibility-seo.js";\nimport "../assets/usage-analytics.js?v=20260817-stage32";\n',
)
patch(
    "assets/web-event-enhancements.js",
    'import "./favorites-web.js?v=20260817";\n',
    'import "./favorites-web.js?v=20260817";\nimport "./usage-analytics.js?v=20260817-stage32";\n',
)
patch(
    "assets/event-page.js",
    '  if (scriptUrl) {\n    import(new URL("./favorites-event-page.js?v=20260817", scriptUrl).href)\n',
    '  if (scriptUrl) {\n    import(new URL("./usage-analytics.js?v=20260817-stage32", scriptUrl).href)\n      .catch(() => {});\n    import(new URL("./favorites-event-page.js?v=20260817", scriptUrl).href)\n',
)

worker = ROOT / "app" / "service-worker.js"
text = worker.read_text(encoding="utf-8")
asset = '"../assets/usage-analytics.js?v=20260817-stage32"'
if asset not in text:
    marker = '"./stage31-accessibility.css",'
    if marker not in text:
        raise SystemExit("STAGE32_ANCHOR_MISSING:app/service-worker.js")
    text = text.replace(marker, marker + f'\n  {asset},', 1)
    worker.write_text(text, encoding="utf-8")

print("STAGE32_ANALYTICS_WIRING_OK")
