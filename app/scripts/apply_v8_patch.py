from pathlib import Path

APP = Path("app")

# Fold visual identity into stable app.css
app_css_path = APP / "app.css"
app_css = app_css_path.read_text(encoding="utf-8")
visual_path = APP / "visual-identity.css"
visual = visual_path.read_text(encoding="utf-8")
marker = "/* Visual identity integrated into the stable app.css shell (PWA v8). */"
if marker not in app_css:
    app_css += "\n\n" + marker + "\n" + visual.strip() + "\n"

detail_css = r'''

/* Internal event detail sheet */
.event-detail-dialog{width:min(760px,calc(100% - 1.4rem));max-height:min(88vh,900px);padding:0;border:0;border-radius:1.6rem;background:transparent;box-shadow:0 30px 100px rgba(8,35,31,.32);overflow:visible}
.event-detail-dialog::backdrop{background:rgba(8,31,28,.62);backdrop-filter:blur(5px)}
.event-detail-panel{position:relative;overflow:auto;max-height:88vh;border-radius:1.6rem;background:var(--surface,#fff);border:1px solid var(--line,#dce5e2)}
.event-detail-close{position:absolute;z-index:4;right:.85rem;top:.85rem;width:2.55rem;height:2.55rem;border-radius:999px;border:1px solid rgba(255,255,255,.7);background:rgba(255,255,255,.94);color:var(--brand-deep,#103c36);font:700 1.5rem/1 system-ui;cursor:pointer;box-shadow:0 6px 20px rgba(15,50,44,.14)}
.event-detail-media{height:min(34vh,300px);overflow:hidden;background:var(--surface-tint,#eef3f1)}
.event-detail-media img{display:block;width:100%;height:100%;object-fit:cover}
.event-detail-content{padding:clamp(1.2rem,4vw,2rem);display:grid;gap:1rem}
.event-detail-meta,.event-detail-badges{display:flex;gap:.45rem;align-items:center;flex-wrap:wrap}
.event-detail-category,.event-detail-type,.event-detail-badge{display:inline-flex;padding:.32rem .58rem;border-radius:999px;font-size:.73rem;font-weight:850}
.event-detail-category{background:color-mix(in srgb,var(--accent) 11%,#fff);color:var(--accent-strong);border:1px solid color-mix(in srgb,var(--accent) 25%,#fff)}
.event-detail-type{background:color-mix(in srgb,var(--brand) 8%,#fff);color:var(--brand)}
.event-detail-badge{background:color-mix(in srgb,var(--accent-2) 20%,#fff);color:var(--brand-deep)}
.event-detail-title{margin:0;color:var(--brand-deep);font-family:Georgia,'Times New Roman',serif;font-size:clamp(1.65rem,4vw,2.5rem);line-height:1.08;letter-spacing:-.025em}
.event-detail-facts,.event-detail-extra{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}
.event-detail-fact{display:grid;grid-template-columns:1.35rem 1fr;gap:.55rem;padding:.75rem;border-radius:1rem;background:color-mix(in srgb,var(--hero-wash) 48%,#fff);border:1px solid var(--line)}
.event-detail-fact-icon{color:var(--accent);font-weight:900;padding-top:.08rem}
.event-detail-fact div{display:grid;gap:.15rem;min-width:0}.event-detail-fact strong{color:var(--brand);font-size:.76rem;text-transform:uppercase;letter-spacing:.045em}.event-detail-fact span{color:var(--ink);line-height:1.4}
.event-detail-description{padding-top:.2rem}.event-detail-description h3{margin:0 0 .45rem;color:var(--brand-deep);font-size:1rem}.event-detail-description p{margin:0;color:var(--muted);line-height:1.65}
.event-detail-actions{display:flex;justify-content:flex-end;gap:.55rem;flex-wrap:wrap;padding-top:.35rem}
.event-detail-action{display:inline-flex;align-items:center;justify-content:center;min-height:2.65rem;padding:.65rem .9rem;border-radius:.8rem;text-decoration:none!important;font-weight:850;font-size:.85rem}
.event-detail-action--primary{background:var(--brand);color:#fff!important;border:1px solid var(--brand)}
.event-detail-action--secondary{background:#fff;color:var(--brand)!important;border:1px solid color-mix(in srgb,var(--brand) 28%,#fff)}
button.card-action{font:inherit;cursor:pointer}
@media(max-width:600px){.event-detail-dialog{width:calc(100% - .8rem);max-height:94vh}.event-detail-panel{max-height:94vh;border-radius:1.25rem}.event-detail-facts,.event-detail-extra{grid-template-columns:1fr}.event-detail-actions{justify-content:stretch}.event-detail-action{flex:1 1 100%}}
'''
if "/* Internal event detail sheet */" not in app_css:
    app_css += detail_css
app_css_path.write_text(app_css, encoding="utf-8")

index_path = APP / "index.html"
index = index_path.read_text(encoding="utf-8")
index = index.replace('  <link rel="stylesheet" href="./visual-identity.css">\n', '')
index = index.replace('<small data-app-version>PWA v6</small>', '<small data-app-version>PWA v8</small>')
index_path.write_text(index, encoding="utf-8")

card_path = APP / "card-experience.js"
card = card_path.read_text(encoding="utf-8")
if not card.startswith('import { openEventDetail } from "./event-detail.js";'):
    card = 'import { openEventDetail } from "./event-detail.js";\n\n' + card

build_anchor = '''function buildAction(href, label, className) {\n  const action = document.createElement("a");\n  action.className = `card-action ${className}`;\n  action.href = href;\n  action.target = "_blank";\n  action.rel = "noopener noreferrer";\n  action.textContent = label;\n  return action;\n}\n'''
if "function buildDetailAction(event, presentation)" not in card:
    detail_builder = build_anchor + '''\nfunction buildDetailAction(event, presentation) {\n  const action = document.createElement("button");\n  action.type = "button";\n  action.className = "card-action card-action--primary";\n  action.dataset.openEvent = event?.id || "event";\n  action.textContent = "Ver evento →";\n  action.addEventListener("click", () => openEventDetail(event, presentation));\n  return action;\n}\n'''
    if card.count(build_anchor) != 1:
        raise SystemExit("buildAction anchor not unique")
    card = card.replace(build_anchor, detail_builder, 1)

old_actions = '''  const official = safeHttpUrl(event?.links?.official || event?.links?.source);\n  const registration = safeHttpUrl(event?.links?.registration || event?.links?.tickets);\n  if (registration && registration !== official) actions.append(buildAction(registration, "Inscribirme", "card-action--secondary"));\n  if (official) actions.append(buildAction(official, "Ver evento →", "card-action--primary"));\n  else if (registration) actions.append(buildAction(registration, "Ver detalles →", "card-action--primary"));\n'''
new_actions = '''  const official = safeHttpUrl(event?.links?.official || event?.links?.source);\n  const registration = safeHttpUrl(event?.links?.registration || event?.links?.tickets);\n  if (registration && registration !== official) actions.append(buildAction(registration, "Inscribirme", "card-action--secondary"));\n  actions.append(buildDetailAction(event, {\n    category: primaryCategory(event),\n    type,\n    labels: [...new Set(labels)],\n    schedule: scheduleLabel(event, config),\n    location: locationLabel(event),\n    price: priceLabel(event),\n    sourceName: sourceLabel,\n    sourceUrl: sourceUrl(event),\n    officialUrl: official,\n    registrationUrl: registration,\n  }));\n'''
if old_actions in card:
    card = card.replace(old_actions, new_actions, 1)
elif new_actions not in card:
    raise SystemExit("rich-card action anchor not found")
card_path.write_text(card, encoding="utf-8")

pwa_path = APP / "pwa.js"
pwa = pwa_path.read_text(encoding="utf-8").replace('const APP_VERSION = "PWA v7";', 'const APP_VERSION = "PWA v8";')
pwa_path.write_text(pwa, encoding="utf-8")

sw_path = APP / "service-worker.js"
sw = sw_path.read_text(encoding="utf-8").replace('const CACHE_VERSION = "v7";', 'const CACHE_VERSION = "v8";')
sw = sw.replace('  "./visual-identity.css",\n', '')
anchor = '  "./card-experience.js",\n'
if '"./event-detail.js"' not in sw:
    sw = sw.replace(anchor, anchor + '  "./event-detail.js",\n', 1)
sw_path.write_text(sw, encoding="utf-8")

for test_name in ("test_pwa.py", "test_multi_city_ui.py"):
    path = APP / "scripts" / test_name
    text = path.read_text(encoding="utf-8")
    text = text.replace("PWA v7", "PWA v8").replace('CACHE_VERSION = "v7"', 'CACHE_VERSION = "v8"')
    if test_name == "test_pwa.py":
        text = text.replace('"./visual-identity.css"', '"./event-detail.js"')
    path.write_text(text, encoding="utf-8")

runtime_path = APP / "scripts" / "test_runtime_browser.py"
runtime = runtime_path.read_text(encoding="utf-8")
fallback_line = "        + '\\n  <script type=\"module\" src=\"./card-image-fallback.js\"></script>'\n"
if "data.visualBrand" not in runtime:
    diagnostic = fallback_line + '''        + '\\n  <script>setTimeout(() => { const root = getComputedStyle(document.documentElement); const card = document.querySelector(".event-card"); const before = card ? getComputedStyle(card, "::before") : null; document.body.dataset.visualBrand = root.getPropertyValue("--brand").trim(); document.body.dataset.visualStripe = before ? before.height : ""; const trigger = document.querySelector("[data-open-event]"); if (trigger) trigger.click(); const detail = document.querySelector("dialog[data-event-detail]"); document.body.dataset.detailOpen = detail && detail.hasAttribute("open") ? "true" : "false"; document.body.dataset.detailHasSource = detail && detail.textContent.includes("Fuente oficial") ? "true" : "false"; }, 6000);</script>'\n'''
    runtime = runtime.replace(fallback_line, diagnostic, 1)

check_anchor = '''        if 'card-action--primary' not in dom:\n            raise AssertionError(f"Primary event action did not render for {city}")\n'''
if "Computed city visual theme did not apply" not in runtime:
    checks = check_anchor + '''        expected_brand = "#15594f" if city == "valparaiso" else "#12556a"\n        if f'data-visual-brand="{expected_brand}"' not in dom:\n            raise AssertionError(f"Computed city visual theme did not apply for {city}")\n        if 'data-visual-stripe="5px"' not in dom:\n            raise AssertionError(f"Computed category card accent did not apply for {city}")\n        if 'data-detail-open="true"' not in dom:\n            raise AssertionError(f"Internal event detail did not open for {city}")\n        if 'data-detail-has-source="true"' not in dom:\n            raise AssertionError(f"Internal event detail did not expose the official source for {city}")\n'''
    runtime = runtime.replace(check_anchor, checks, 1)
runtime_path.write_text(runtime, encoding="utf-8")

contract = APP / "scripts" / "test_internal_details_v8.py"
contract.write_text('''from pathlib import Path\nAPP = Path("app")\nindex = (APP / "index.html").read_text(encoding="utf-8")\ncss = (APP / "app.css").read_text(encoding="utf-8")\ncard = (APP / "card-experience.js").read_text(encoding="utf-8")\npwa = (APP / "pwa.js").read_text(encoding="utf-8")\nsw = (APP / "service-worker.js").read_text(encoding="utf-8")\nassert "visual-identity.css" not in index\nassert "Visual identity integrated into the stable app.css shell" in css\nassert "event-detail-dialog" in css\nassert 'import { openEventDetail } from "./event-detail.js";' in card\nassert "dataset.openEvent" in card\nassert 'buildAction(official, "Ver evento' not in card\nassert 'const APP_VERSION = "PWA v8";' in pwa\nassert 'const CACHE_VERSION = "v8";' in sw\nassert '"./event-detail.js"' in sw\nprint("Internal event detail + stable visual shell v8 contract: OK")\n''', encoding="utf-8")

print("v8 patch applied")
