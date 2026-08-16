from pathlib import Path
APP = Path("app")
index = (APP / "index.html").read_text(encoding="utf-8")
css = (APP / "app.css").read_text(encoding="utf-8")
card = (APP / "card-experience.js").read_text(encoding="utf-8")
pwa = (APP / "pwa.js").read_text(encoding="utf-8")
sw = (APP / "service-worker.js").read_text(encoding="utf-8")
assert "visual-identity.css" not in index
assert "Visual identity integrated into the stable app.css shell" in css
assert "event-detail-dialog" in css
assert 'import { openEventDetail } from "./event-detail.js";' in card
assert "dataset.openEvent" in card
assert 'buildAction(official, "Ver evento' not in card
assert 'const APP_VERSION = "PWA v8";' in pwa
assert 'const CACHE_VERSION = "v8";' in sw
assert '"./event-detail.js"' in sw
print("Internal event detail + stable visual shell v8 contract: OK")
