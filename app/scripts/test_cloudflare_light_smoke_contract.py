from pathlib import Path

WORKFLOW = Path(".github/workflows/sync-cloudflare-preview.yml").read_text(encoding="utf-8")

required = (
    "Lightweight smoke of vivamos.pages.dev",
    "https://vivamos.pages.dev",
    "/app/event-detail.js",
    "/app/data/gijon/agenda_web.json",
    "/agenda_web.json",
    "hashlib.sha256",
    "CLOUDFLARE_DEPLOY_MATCH",
    "CLOUDFLARE_LIGHT_HTTP_OK city={city}",
    "CLOUDFLARE_LIGHT_SMOKE_OK",
    "python app/scripts/test_gijon_source_detail.py",
)
for marker in required:
    assert marker in WORKFLOW, f"Cloudflare lightweight smoke contract is missing: {marker}"

push_index = WORKFLOW.index("Push synchronized Cloudflare branch")
smoke_index = WORKFLOW.index("Lightweight smoke of vivamos.pages.dev")
assert push_index < smoke_index, "Cloudflare smoke must run only after the deployment branch is pushed"

for forbidden in ("google-chrome", "chromium", "upload-artifact", "actions/upload-artifact"):
    assert forbidden not in WORKFLOW.lower(), f"Lightweight smoke must not use heavy browser/artifact step: {forbidden}"

assert "range(1, 13)" in WORKFLOW
assert "time.sleep(5)" in WORKFLOW

print("Cloudflare lightweight smoke workflow contract: OK")
