import re
from pathlib import Path

APP = Path("app")
sw = (APP / "service-worker.js").read_text(encoding="utf-8")
release = (APP / "release-version.js").read_text(encoding="utf-8")
app_js = (APP / "app.js").read_text(encoding="utf-8")
app_core = (APP / "app-core.js").read_text(encoding="utf-8")
temporal_core = (APP / "temporal-priority-core.mjs").read_text(encoding="utf-8")
agenda_order = (APP / "agenda-order-core.mjs").read_text(encoding="utf-8")
exhibition_guard = (APP / "exhibition-presentation-guard.js").read_text(encoding="utf-8")
data_pipeline = (APP / "data-pipeline.js").read_text(encoding="utf-8")

# Warm shell navigations remain cache-first for startup speed. Agenda datasets
# are publication state and must be network-first so a certified publication is
# visible on the first successful load; their cache is offline fallback only.
assert "async function cacheFirstNavigation(request, event)" in sw
assert "event.respondWith(cacheFirstNavigation(request, event));" in sw
assert "event.waitUntil(refreshShell(cache, request).then(() => undefined));" in sw
assert "async function networkFirstNavigation" not in sw

assert "async function networkFirstDataset(request)" in sw
assert "return networkFirstDataset(request);" in sw
assert "async function cacheFirstDataset" not in sw
dataset_block = sw.split("async function networkFirstDataset", 1)[1].split('self.addEventListener("fetch"', 1)[0]
assert dataset_block.index("fetchAndCacheDataset(cache, request)") < dataset_block.index("cache.match(request")
assert "event.waitUntil(fetchAndCacheDataset(cache, request).then(() => undefined));" not in dataset_block
assert "DATA_NETWORK_BUDGET_MS" not in sw
assert "Promise.race" not in sw

# release-version.js remains network-first so clients can discover a new PWA
# generation. Ordinary shell startup remains cache-first; dataset freshness is
# independently network-first with offline fallback.
assert 'requestUrl.pathname.endsWith("/release-version.js")' in sw
assert "networkFirstFreshShell(request)" in sw
match = re.search(r"const\s+RELEASE\s*=\s*(\d+)\s*;", release)
assert match and int(match.group(1)) >= 177

# Post-render presentation work must yield to the browser. Point 4/5 semantics
# remain in temporal-priority-core; the shared agenda-order authority composes
# them before optional local presentation tie-breaks, without moving sort work
# back into the hot filter-render path.
assert "function runWhenMainThreadIsIdle(callback)" in app_js
assert "requestIdleCallback" in app_js
assert "runWhenMainThreadIsIdle(() => { void loadOptionalEnhancements(); });" in app_js
assert "requestAnimationFrame(applyTemporalOrderPolicy)" in app_js
assert "queueMicrotask(applyTemporalOrderPolicy)" not in app_js
assert "const DATE_FORMATTERS = new Map();" in temporal_core
assert "dateFormatterForCity" in temporal_core
assert "compareAgendaSemanticPriority" in agenda_order
assert "classifyTemporalEvent" in agenda_order
assert "compareAgendaOrder" in app_js
assert "requestAnimationFrame(applyGuard)" in exhibition_guard
assert "queueMicrotask(applyGuard)" not in exhibition_guard

# Once raw payloads are already in the service-worker cache, repeat openings
# must not redo every sanitizer/normalizer/deduplication pass. The processed
# result is keyed only by release and source generation. Time-dependent
# visibility is materialized after every cache read, so cached normalization can
# never freeze a previous day's visible set.
assert 'const PROCESSED_CACHE_PREFIX = "vivamos-processed-pipeline-";' in data_pipeline
assert "function buildSourceSignature(city, base, supplementalResult)" in data_pipeline
assert "generated_at" in data_pipeline
assert "localDateKey(now" not in data_pipeline
assert "async function readProcessedResult(city, signature)" in data_pipeline
assert "async function writeProcessedResult(city, signature, result)" in data_pipeline
assert "materializeRuntimeResult(cached, city, now, diagnostics)" in data_pipeline
assert "visibilityDecisions" in data_pipeline
assert 'diagnostics.push({ name: "processed-pipeline-cache", status: "hit" });' in data_pipeline
assert "publishAgendaRuntimeSnapshot(city, result);\n      return result;" in data_pipeline

# v177 moves repeated render work out of the hot path. These are structural
# guards rather than fragile timing thresholds: CI should fail if later edits
# start sorting the whole dataset, rebuilding source/category DOM, or creating
# date formatters on every filter render again. The shared agenda comparator
# remains the only visible ordering authority.
for marker in (
    "const formatterCache = new Map();",
    "let searchHaystackCache = new WeakMap();",
    "sortedEvents = sortAgendaEvents(allEvents);",
    "function computeSectionCounts(events)",
    "grid.replaceChildren(fragment);",
    "function scheduleSourcesRender()",
    'requestIdleCallback(run, { timeout: 1200 })',
    "scheduleSourcesRender();",
):
    assert marker in app_core, f"v177 app-core performance contract missing: {marker}"

render_events = app_core.split("function renderEvents()", 1)[1].split("function resetDiscoveryFilters()", 1)[0]
assert "renderSources();" not in render_events
assert "renderCategories();" not in render_events
assert "return sortAgendaEvents(allEvents.filter" not in app_core
assert "allEvents.filter((event) => eventMatchesSection" not in app_core

print("PWA shell-cache and network-first dataset regression: OK")
