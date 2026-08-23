from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__temporal_priority_browser_test.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def check_ui_removed() -> None:
    module = (APP / "temporal-priority.js").read_text(encoding="utf-8")
    core = (APP / "temporal-priority-core.mjs").read_text(encoding="utf-8")
    agenda_order = (APP / "agenda-order-core.mjs").read_text(encoding="utf-8")
    visibility_core = (APP / "visibility-owner-core.mjs").read_text(encoding="utf-8")
    combined = (APP / "combined-filters.js").read_text(encoding="utf-8")
    runtime_state = (APP / "agenda-runtime-state.mjs").read_text(encoding="utf-8")
    entry = (APP / "app.js").read_text(encoding="utf-8")

    for removed_marker in (
        "Hoy / No te lo pierdas",
        "Terminan pronto",
        "Próximos eventos puntuales",
        "Exposiciones y muestras vigentes",
        "PRIORITY_BLOCKS",
        "renderPriority",
        "temporalBadge(",
    ):
        assert removed_marker not in module, f"removed temporal UI returned: {removed_marker}"

    assert "shouldSuppressForTemporalFilter" not in module, "temporal presentation must not own visibility"
    assert "shouldSuppressForTemporalFilter" in visibility_core, "date-confidence filter guard must remain active in the visibility core"
    assert "visibility-owner-core.mjs" in combined, "combined filters must consume the canonical visibility core"
    assert "dataset.temporalSuppressed" in combined, "combined filters must own temporal visual suppression"
    assert "removeLegacyTemporalUi" in module, "legacy temporal UI cleanup must remain active"
    assert "const CITY_REGISTRY = await" not in module, "temporal cleanup must not block app startup on top-level await"
    common_runtime = entry.split("const OPTIONAL_MODULES = [", 1)[1].split("];", 1)[0]
    assert 'temporal-priority.js?v=' in common_runtime, "app common runtime must retain non-blocking temporal cleanup"
    assert "GIJON_DEFERRED_MODULES" not in entry, "temporal presentation must not be selected by city"

    # Point 4/5 semantics remain in temporal-priority-core. The canonical
    # agenda-order authority composes those shared temporal primitives before
    # optional local presentation tie-breaks, so top-level renderers never own
    # an independent temporal comparator.
    assert "export const LONG_RUNNING_DAYS = 7" in core, "long-running threshold must remain seven days in the shared core"
    assert '"this_weekend"' in core and '"always_available"' in core, "shared core must expose the six-bucket hierarchy"
    assert "classifyContentKind" in core, "content_kind classification must be owned by the shared temporal core"
    assert 'Symbol.for("vivamos.agendaRuntimeState")' in runtime_state, "runtime snapshot must remain shared across versioned module identities"
    assert "compareAgendaOrder" in entry, "rendered cards must consume the canonical agenda order"
    assert "compareTemporalPriority" not in entry, "app entrypoint must not bypass the canonical agenda-order authority"
    assert "compareAgendaSemanticPriority" in agenda_order, "canonical agenda order must expose shared temporal-first semantics"
    assert "classifyTemporalEvent" in agenda_order, "canonical agenda order must consume temporal classification from temporal-priority-core"
    assert "classifyTemporalEvent" in entry, "rendered cards must expose content kind and temporal bucket metadata"
    assert "orderingCardEventIds" in entry, "group ordering must resolve the events represented by each card"
    assert "visibleOnly: !card.hidden" in entry, "filtered grouped cards must be ordered from their currently visible events"
    assert "data-filter-summary" in entry and "filterSummary" in entry, "date/area/search filters must trigger ordering after visibility settles"
    assert "orderingIsLongExhibition" not in entry, "special-case long-exhibition ordering must not return"
    assert "categoryFilterIsActive" not in entry, "category-dependent temporal ordering must not return"
    assert "placeExhibitionsLast" not in entry, "legacy all-exhibitions-last policy must not return"


def make_page() -> None:
    TEST_PAGE.write_text(
        r'''<!doctype html>
<html><body>
<script type="module">
import {
  classifyContentKind,
  classifyTemporalEvent,
  organizeTemporalPriority,
  temporalBadge,
} from "./temporal-priority-core.mjs";

const valpo = { id: "valparaiso", timezone: "America/Santiago", locale: "es-CL" };
const gijon = { id: "gijon", timezone: "Europe/Madrid", locale: "es-ES" };
const instant = new Date("2026-08-19T00:30:00Z");
const event = (id, start, end, startConfidence, endConfidence, category = "musica", options = {}) => ({
  id,
  title: id,
  event_type: options.eventType || "event",
  primary_category: { id: category, label: category === "exposiciones" ? "Exposiciones" : "Música" },
  categories: [],
  description: options.description || "",
  schedule: {
    start,
    end,
    display_text: options.displayText || "",
    start_confidence: startConfidence,
    end_confidence: endConfidence,
    occurrences: [],
  },
});

const explicit = event("explicit", "2026-08-19", null, "explicit", null);
const fallback = event("fallback", "2026-08-19", "2026-08-30", "technical_fallback", "explicit", "exposiciones");
const closing = event("closing", "2026-08-01", "2026-08-21", "technical_fallback", "official_revalidation");
const unreliableClose = event("bad-close", "2026-08-01", "2026-08-21", "explicit", "technical_fallback");

const gijonBlocks = organizeTemporalPriority([explicit, fallback, closing, unreliableClose], gijon, instant);
const valpoBlocks = organizeTemporalPriority([explicit, fallback, closing, unreliableClose], valpo, instant);

const hierarchyNow = new Date("2026-08-21T12:00:00Z");
const weekendLong = event("weekend-long", "2026-08-22", "2026-09-30", "explicit", "explicit", "exposiciones");
const weekendSingle = event("weekend-single", "2026-08-22", null, "explicit", null);
const recurring = event("recurring", null, null, null, null, "musica", {
  eventType: "flexible_offer",
  displayText: "Lunes a viernes, desde las 18:20",
});
const hierarchyBlocks = organizeTemporalPriority([weekendLong, weekendSingle, recurring], valpo, hierarchyNow);
const recurringState = classifyTemporalEvent(recurring, valpo, hierarchyNow);

const runtimeWriter = await import("./agenda-runtime-state.mjs?browser-writer");
const runtimeReader = await import("./agenda-runtime-state.mjs?browser-reader");
runtimeWriter.clearAgendaRuntimeSnapshot();
const runtimeResult = { dataset: { events: [recurring] }, diagnostics: [] };
runtimeWriter.publishAgendaRuntimeSnapshot(valpo, runtimeResult);
const runtimeShared = runtimeReader.getAgendaRuntimeSnapshot("valparaiso");
const runtimeSharedOk = Boolean(
  runtimeShared?.events?.[0]?.content_kind === "recurring_offer" &&
  runtimeShared?.events?.[0]?.temporal_bucket === "always_available" &&
  runtimeResult.dataset.events[0]?.content_kind === "recurring_offer" &&
  runtimeResult.dataset.events[0]?.temporal_bucket === "always_available"
);

document.body.dataset.temporalBrowserDone = "true";
document.body.dataset.gijonToday = String(gijonBlocks.today.some((item) => item.id === "explicit"));
document.body.dataset.valpoToday = String(valpoBlocks.today.some((item) => item.id === "explicit"));
document.body.dataset.fallbackToday = String(gijonBlocks.today.some((item) => item.id === "fallback"));
document.body.dataset.reliableClosing = String(gijonBlocks.endingSoon.some((item) => item.id === "closing"));
document.body.dataset.unreliableClosing = String(gijonBlocks.endingSoon.some((item) => item.id === "bad-close"));
document.body.dataset.fallbackBadge = String(temporalBadge(fallback, gijon, instant) || "");
document.body.dataset.closingBadge = String(temporalBadge(closing, gijon, instant) || "");
document.body.dataset.weekendOrder = hierarchyBlocks.thisWeekend.map((item) => item.id).join(",");
document.body.dataset.recurringKind = classifyContentKind(recurring, valpo);
document.body.dataset.recurringBucket = recurringState.bucket;
document.body.dataset.runtimeShared = String(runtimeSharedOk);
</script>
</body></html>''',
        encoding="utf-8",
    )


def dump_dom(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="vivamos-temporal-browser-", ignore_cleanup_errors=True) as profile:
        cmd = [
            chrome_binary(),
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-extensions",
            "--disable-sync",
            "--no-first-run",
            "--no-default-browser-check",
            "--virtual-time-budget=900",
            f"--user-data-dir={profile}",
            "--dump-dom",
            url,
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=20)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome temporal guard probe failed: {result.stderr[-1200:]}")
        return result.stdout


def main() -> None:
    check_ui_removed()
    os.chdir(ROOT)
    make_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            dom = dump_dom(f"http://127.0.0.1:{port}/app/__temporal_priority_browser_test.html")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)

    expected = {
        'data-temporal-browser-done="true"': "temporal core did not execute in Chrome",
        'data-gijon-today="true"': "Europe/Madrid did not classify the explicit event as today",
        'data-valpo-today="false"': "America/Santiago incorrectly classified the same date as today",
        'data-fallback-today="false"': "technical_fallback created a false Hoy",
        'data-reliable-closing="true"': "reliable ending-soon event was not surfaced by the core",
        'data-unreliable-closing="false"': "unreliable end created ending-soon status",
        'data-fallback-badge=""': "technical fallback generated an affirmative badge in the core",
        'data-closing-badge="Últimos 3 días"': "reliable closing badge core contract changed unexpectedly",
        'data-weekend-order="weekend-single,weekend-long"': "punctual weekend event did not outrank long-running content",
        'data-recurring-kind="recurring_offer"': "recurring flexible offer did not get recurring_offer content_kind",
        'data-recurring-bucket="always_available"': "recurring offer did not land in always_available",
        'data-runtime-shared="true"': "versioned runtime modules did not share one temporal snapshot",
    }
    for marker, message in expected.items():
        if marker not in dom:
            raise AssertionError(message)
    print("Temporal hierarchy, content_kind, shared runtime, timezone and confidence browser contracts: OK")


if __name__ == "__main__":
    main()
