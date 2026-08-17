from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app" / "index.html"
text = path.read_text(encoding="utf-8")

css = '  <link rel="stylesheet" href="./stage31-accessibility.css?v=20260817" data-stage31-accessibility>'
if css not in text:
    anchor = '  <link rel="stylesheet" href="./app.css">'
    if anchor not in text:
        raise SystemExit("APP_CSS_ANCHOR_MISSING")
    text = text.replace(anchor, anchor + "\n" + css, 1)

if '<main id="contenido" tabindex="-1">' not in text:
    anchor = '<main id="contenido">'
    if anchor not in text:
        raise SystemExit("APP_MAIN_ANCHOR_MISSING")
    text = text.replace(anchor, '<main id="contenido" tabindex="-1">', 1)

path.write_text(text, encoding="utf-8")
print("STAGE31_APP_PATCH_OK")
