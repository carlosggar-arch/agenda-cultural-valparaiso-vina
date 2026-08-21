import re
from pathlib import Path

APP = Path("app")
sw = (APP / "service-worker.js").read_text(encoding="utf-8")
release = (APP / "release-version.js").read_text(encoding="utf-8")
app_js = (APP / "app.js").read_text(encoding="utf-8")
exhibition_guard = (APP / "exhibition-presentation-guard.js").read_text(encoding="utf-8")
data_pipeline = (APP / "data-pipeline.js").read_text(encoding="utf-8")

# Warm starts must not wait for the network: both the HTML navigation and
# already-cached datasets are returned immediately while a refresh is attached
# to the fetch event lifecycle.
assert "async function cacheFirstNavigation(request, event)" in sw
assert "event.respondWith(cacheFirstNavigation(request, event));" in sw
assert "event.waitUntil(refreshShell(cache, request).then(() => undefined));" in sw
assert "async function networkFirstNavigation" not in sw

assert "async function cacheFirstDataset(request, event)" in sw
assert "return cacheFirstDataset(request, event);" in sw
assert "event.waitUntil(fetchAndCacheDataset(cache, request).then(() => undefined));" in sw
assert "DATA_NETWORK_BUDGET_MS" not in sw
assert "Promise.race" not in sw

# release-version.js remains network-first so clients can discover a new PWA
# generation even though ordinary shell/data startup is cache-first. The
# cache-first contract was introduced in v170 and must survive later releases.
assert 'requestUrl.pathname.endsWith("/release-version.js")' in sw
assert "networkFirstFreshShell(request)" in sw
match = re.search(r"const\s+RELEASE\s*=\s*(\d+)\s*;", release)
assert match and int(match.group(1)) >= 170

# Post-render presentation work must yield to the browser. This keeps mobile
# paint/input responsive while preserving the same eventual visual result.
assert "function runWhenMainThreadIsIdle(callback)" in app_js
assert "requestIdleCallback" in app_js
assert "runWhenMainThreadIsIdle(() => { void loadOptionalEnhancements(); });" in app_js
assert "requestAnimationFrame(applyExhibitionOrderPolicy)" in app_js
assert "queueMicrotask(applyExhibitionOrderPolicy)" not in app_js
assert "const orderingDateFormatters = new Map();" in app_js
assert "requestAnimationFrame(applyGuard)" in exhibition_guard
assert "queueMicrotask(applyGuard)" not in exhibition_guard

# Once raw payloads are already in the service-worker cache, repeat openings
# must not redo every sanitizer/normalizer/deduplication pass. The processed
# result is keyed by release, source generation and local day so data changes or
# the midnight expiry boundary invalidate it automatically.
assert 'const PROCESSED_CACHE_PREFIX = "vivamos-processed-pipeline-";' in data_pipeline
assert "function buildSourceSignature(city, base, supplementalResult, now)" in data_pipeline
assert "generated_at" in data_pipeline
assert "localDateKey(now" in data_pipeline
assert "async function readProcessedResult(city, signature)" in data_pipeline
assert "async function writeProcessedResult(city, signature, result)" in data_pipeline
assert 'diagnostics.push({ name: "processed-pipeline-cache", status: "hit" });' in data_pipeline
assert "publishAgendaRuntimeSnapshot(city, result);\n      return result;" in data_pipeline

print("PWA cache-first startup regression: OK")
