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
TEST_PAGE = APP / "__runtime_test.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


class RuntimeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def make_test_page(city: str) -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    app_marker = '<script type="module" src="./app.js"></script>'
    combined_marker = '<script type="module" src="./combined-filters-bootstrap.js"></script>'
    pwa_marker = '<script type="module" src="./pwa.js"></script>'
    if app_marker not in source or combined_marker not in source or pwa_marker not in source:
        raise AssertionError("app.js/combined-filters-bootstrap.js/pwa.js script marker not found")
    source = source.replace(combined_marker, "", 1).replace(pwa_marker, "", 1)

    # Keep this browser contract intentionally short. Long virtual-time probes have
    # become unstable on GitHub's hosted Chrome image (DBus/GCM crash before dump-dom),
    # while the same app succeeds in short first-render and production smoke probes.
    # Dedicated interaction tests cover details, sharing, install and favorites.
    diagnostic = r'''
  <script>
    (() => {
      const visibleCards = () => [...document.querySelectorAll(".event-card[data-event-id]")]
        .filter((card) => !card.hidden && getComputedStyle(card).display !== "none");
      const allCards = () => [...document.querySelectorAll(".event-card[data-event-id]")];
      const started = performance.now();

      const finish = () => {
        const initialVisible = visibleCards().length;
        const cityTitle = document.querySelector("[data-header-city-title]");
        const areaGroup = document.querySelector("[data-area-filter-group]");
        const sourceSection = document.querySelector("[data-sources-section]");
        const sourceToggle = document.querySelector("[data-sources-toggle]");

        document.body.dataset.runtimeDiagnosticDone = "true";
        document.body.dataset.cityTitle = cityTitle?.textContent || "";
        document.body.dataset.cityTitleWhiteSpace = cityTitle ? getComputedStyle(cityTitle).whiteSpace : "";
        document.body.dataset.combinedWorkbench = document.querySelector(".filter-workbench") ? "true" : "false";
        document.body.dataset.combinedWhen = document.querySelector("[data-combined-when]") ? "true" : "false";
        document.body.dataset.combinedCategories = document.querySelectorAll("[data-combined-category]").length > 0 ? "true" : "false";
        document.body.dataset.accessFilterAbsent = document.querySelector("[data-combined-access]") ? "false" : "true";
        document.body.dataset.formatFilterAbsent = document.querySelector("[data-combined-format]") ? "false" : "true";
        document.body.dataset.audienceFilterAbsent = document.querySelector("[data-combined-audience]") ? "false" : "true";
        document.body.dataset.priceFilterAbsent = document.querySelector("[data-combined-price]") ? "false" : "true";
        document.body.dataset.areaFilterHidden = areaGroup && getComputedStyle(areaGroup).display === "none" ? "true" : "false";
        document.body.dataset.gijonVisualReference = document.querySelector("[data-gijon-visual-reference]") ? "true" : "false";
        document.body.dataset.sourcesDefaultHidden = sourceSection && getComputedStyle(sourceSection).display === "none" ? "true" : "false";
        sourceToggle?.click();
        document.body.dataset.sourcesAfterOpen = sourceSection && getComputedStyle(sourceSection).display !== "none" ? "true" : "false";
        document.body.dataset.visibleBeforeFilter = String(initialVisible);

        const candidates = [...document.querySelectorAll('[data-combined-when] [data-filter-value]')]
          .filter((button) => !["todos", "personalizado"].includes(button.dataset.filterValue))
          .map((button) => ({ button, count: Number(button.querySelector("[data-combined-count]")?.textContent || -1) }))
          .filter((item) => Number.isFinite(item.count) && item.count !== initialVisible);
        const dateChoice = candidates[0]?.button || document.querySelector('[data-combined-when] [data-filter-value="7-dias"]');
        dateChoice?.click();

        setTimeout(() => {
          const afterDate = visibleCards().length;
          const hiddenCards = allCards().filter((card) => card.hidden);
          document.body.dataset.visibleAfterFilter = String(afterDate);
          document.body.dataset.filterActuallyChanged = String(afterDate !== initialVisible);
          document.body.dataset.hiddenCardsSuppressed = String(
            hiddenCards.length > 0 && hiddenCards.every((card) => getComputedStyle(card).display === "none")
          );
          document.body.dataset.filterUrlWhen = new URLSearchParams(location.search).get("when") || "";

          if (document.documentElement.dataset.city === "valparaiso") {
            document.querySelector('[data-combined-area] [data-filter-value="valparaiso"]')?.click();
          }
          setTimeout(() => {
            const params = new URLSearchParams(location.search);
            document.body.dataset.filterUrlArea = params.get("area") || "";
            document.body.dataset.removedParamsAbsent = String(!params.has("access") && !params.has("format") && !params.has("aud"));
          }, 120);
        }, 180);
      };

      const ready = () => visibleCards().length > 0
        && document.querySelector("[data-combined-when]")
        && document.querySelectorAll("[data-combined-category]").length > 0;
      const timer = setInterval(() => {
        if (ready() || performance.now() - started > 1800) {
          clearInterval(timer);
          finish();
        }
      }, 60);
    })();
  </script>'''

    injection = (
        f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>\n  ' + app_marker
        + '\n  <script type="module" src="./combined-filters-bootstrap.js"></script>'
        + '\n  <script type="module" src="./card-experience.js"></script>'
        + '\n  <script type="module" src="./schedule-display.js"></script>'
        + '\n  <script type="module" src="./card-image-fallback.js"></script>'
        + '\n  <script type="module" src="./compact-top.js"></script>'
        + '\n  <script type="module" src="./gijon-visual-reference.js"></script>'
        + '\n  <script type="module" src="./sources-toggle.js"></script>'
        + '\n  <script type="module" src="./header-redesign.js"></script>'
        + '\n  <script type="module" src="./density-polish.js"></script>'
        + '\n  <script type="module" src="./combined-filters-polish.js"></script>' + diagnostic
    )
    TEST_PAGE.write_text(source.replace(app_marker, injection, 1), encoding="utf-8")


def dump_dom(city: str, url: str) -> str:
    errors: list[str] = []
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"agenda-runtime-{city}-{attempt}-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--window-size=1280,900", "--virtual-time-budget=3200",
                f"--user-data-dir={profile}", "--dump-dom", url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=30)
            except subprocess.TimeoutExpired:
                errors.append(f"attempt {attempt}: Chrome timed out")
                time.sleep(0.5)
                continue
            if result.returncode == 0 and result.stdout:
                return result.stdout
            errors.append(f"attempt {attempt}: exit={result.returncode}; stderr={result.stderr[-1000:]}")
            time.sleep(0.5)
    raise AssertionError(f"Chrome runtime probe failed for {city}: {' | '.join(errors)}")


def run_city(city: str, base_url: str) -> None:
    make_test_page(city)
    dom = dump_dom(city, f"{base_url}/app/__runtime_test.html")
    if dom.count('class="event-card') <= 0:
        raise AssertionError(f"No event cards rendered for {city}")
    if f'data-city="{city}"' not in dom:
        raise AssertionError(f"Active city context did not apply for {city}")
    for marker, message in (
        ('data-runtime-diagnostic-done="true"', "runtime diagnostic did not finish"),
        ('data-combined-workbench="true"', "combined workbench missing"),
        ('data-combined-when="true"', "date filter missing"),
        ('data-access-filter-absent="true"', "access filter still visible"),
        ('data-format-filter-absent="true"', "format filter still visible"),
        ('data-audience-filter-absent="true"', "audience filter still visible"),
        ('data-combined-categories="true"', "category filters missing"),
        ('data-price-filter-absent="true"', "price filter still visible"),
        ('data-removed-params-absent="true"', "removed filter parameters still active"),
        ('data-filter-actually-changed="true"', "date filter did not change visible results"),
        ('data-hidden-cards-suppressed="true"', "filtered cards remain visually displayed"),
        ('data-sources-default-hidden="true"', "sources visible by default"),
        ('data-sources-after-open="true"', "sources did not open"),
        ('data-city-title-white-space="nowrap"', "city title wraps"),
    ):
        if marker not in dom:
            raise AssertionError(f"{message} for {city}")
    if 'data-filter-url-when=""' in dom:
        raise AssertionError(f"Date filter did not persist in URL for {city}")
    expected_title = "Valparaíso / Viña del Mar" if city == "valparaiso" else "Gijón / Xixón"
    if f'data-city-title="{expected_title}"' not in dom:
        raise AssertionError(f"Unexpected city title for {city}")
    if city == "valparaiso":
        assert 'data-filter-url-area="valparaiso"' in dom
        assert 'data-area-filter-hidden="false"' in dom
    else:
        assert 'data-area-filter-hidden="true"' in dom
        assert 'data-filter-url-area=""' in dom
        assert 'data-gijon-visual-reference="true"' in dom
        assert "https://www.gijon.es/app/actividades/oferta" in dom
    if 'class="event-card-source"' not in dom or 'class="source-card"' not in dom:
        raise AssertionError(f"Source data unavailable for {city}")
    if city == "valparaiso" and 'data-image-kind="category-fallback"' not in dom:
        raise AssertionError("Valparaiso category image fallback missing")
    if 'No te lo pierdas' not in dom:
        raise AssertionError(f"Featured badge missing for {city}")
    print(f"Browser runtime {city}: controls render and filtering updates the visible card set")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with RuntimeServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); time.sleep(0.2)
        try:
            for city in ("valparaiso", "gijon"):
                run_city(city, f"http://127.0.0.1:{port}")
        finally:
            server.shutdown(); thread.join(timeout=2); TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
