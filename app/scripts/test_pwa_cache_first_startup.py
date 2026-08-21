from pathlib import Path

APP = Path("app")
sw = (APP / "service-worker.js").read_text(encoding="utf-8")
release = (APP / "release-version.js").read_text(encoding="utf-8")
app_js = (APP / "app.js").read_text(encoding="utf-8")

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
# generation even though ordinary shell/data startup is cache-first.
assert 'requestUrl.pathname.endsWith("/release-version.js")' in sw
assert "networkFirstFreshShell(request)" in sw
assert "const RELEASE = 171;" in release

# After coreReady, secondary presentation work must yield to the browser so the
# first rendered screen can paint/respond before optional enrichers and ordering.
assert "function runWhenMainThreadIsIdle(callback)" in app_js
assert "requestIdleCallback" in app_js
assert "runWhenMainThreadIsIdle(() => { void loadOptionalEnhancements(); });" in app_js
assert "requestAnimationFrame(applyExhibitionOrderPolicy)" in app_js
assert "queueMicrotask(applyExhibitionOrderPolicy)" not in app_js
assert "const orderingDateFormatters = new Map();" in app_js

print("PWA cache-first startup regression: OK")
