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


def make_test_page(city: str) -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    app_marker = '<script type="module" src="./app.js"></script>'
    combined_marker = '<script type="module" src="./combined-filters.js"></script>'
    pwa_marker = '<script type="module" src="./pwa.js"></script>'
    if app_marker not in source or combined_marker not in source or pwa_marker not in source:
        raise AssertionError("app.js/combined-filters.js/pwa.js script marker not found")
    source = source.replace(combined_marker, "", 1).replace(pwa_marker, "", 1)

    diagnostic = r'''
  <script>
    setTimeout(() => {
      const sourceSection = document.querySelector("[data-sources-section]");
      const sourceToggle = document.querySelector("[data-sources-toggle]");
      document.body.dataset.gijonVisualReference = document.querySelector("[data-gijon-visual-reference]") ? "true" : "false";
      document.body.dataset.sourcesDefaultHidden = sourceSection && getComputedStyle(sourceSection).display === "none" ? "true" : "false";
      sourceToggle?.click();
      document.body.dataset.sourcesAfterOpen = sourceSection && getComputedStyle(sourceSection).display !== "none" ? "true" : "false";
      const cityTitle = document.querySelector("[data-header-city-title]");
      const searchToggle = document.querySelector("[data-header-search-toggle]");
      const searchPopover = document.querySelector("[data-header-search-popover]");
      document.body.dataset.cityTitle = cityTitle?.textContent || "";
      document.body.dataset.cityTitleWhiteSpace = cityTitle ? getComputedStyle(cityTitle).whiteSpace : "";
      document.body.dataset.searchTogglePresent = searchToggle ? "true" : "false";
      document.body.dataset.searchInitiallyHidden = searchPopover?.hidden ? "true" : "false";
      searchToggle?.click();
      document.body.dataset.searchAfterOpen = searchPopover && !searchPopover.hidden ? "true" : "false";
      document.body.dataset.searchInputVisible = document.querySelector("[data-smart-search]") && searchPopover && !searchPopover.hidden ? "true" : "false";
      document.body.dataset.combinedWorkbench = document.querySelector(".filter-workbench") ? "true" : "false";
      document.body.dataset.combinedWhen = document.querySelector("[data-combined-when]") ? "true" : "false";
      document.body.dataset.combinedPrice = document.querySelector("[data-combined-price]") ? "true" : "false";
      document.body.dataset.combinedCategories = document.querySelectorAll("[data-combined-category]").length > 0 ? "true" : "false";
      const areaGroup = document.querySelector("[data-area-filter-group]");
      document.body.dataset.areaFilterHidden = areaGroup && getComputedStyle(areaGroup).display === "none" ? "true" : "false";
      const city = document.documentElement.dataset.city;
      if (city === "valparaiso") document.querySelector('[data-combined-area] [data-filter-value="valparaiso"]')?.click();
      document.querySelector('[data-combined-price] [data-filter-value="gratis"]')?.click();
      setTimeout(() => {
        const params = new URLSearchParams(location.search);
        document.body.dataset.filterUrlPrice = params.get("price") || "";
        document.body.dataset.filterUrlArea = params.get("area") || "";
        const trigger = document.querySelector("[data-open-event]");
        trigger?.click();
        const detail = document.querySelector("dialog[data-event-detail]");
        const detailText = detail?.textContent || "";
        document.body.dataset.detailOpen = detail?.hasAttribute("open") ? "true" : "false";
        document.body.dataset.detailHasSource = detail && (detailText.includes("Fuente oficial") || detailText.includes("Datos oficiales")) ? "true" : "false";
      }, 450);
    }, 5200);
  </script>'''

    injection = (
        f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>\n  ' + app_marker
        + '\n  <script type="module" src="./combined-filters.js"></script>'
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


def dump_dom_with_retry(city: str, url: str) -> str:
    errors: list[str] = []
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"agenda-{city}-chrome-{attempt}-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
                "--virtual-time-budget=8000", f"--user-data-dir={profile}", "--dump-dom", url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=40)
            except subprocess.TimeoutExpired:
                errors.append(f"attempt {attempt}: Chrome timed out")
                time.sleep(1)
                continue
            if result.returncode == 0 and result.stdout:
                return result.stdout
            errors.append(f"attempt {attempt}: exit={result.returncode}; stderr={result.stderr[-1200:]}")
            time.sleep(1)
    raise AssertionError(f"Chrome runtime probe failed for {city} after two isolated attempts: {' | '.join(errors)}")


def run_city(city: str, base_url: str) -> None:
    make_test_page(city)
    dom = dump_dom_with_retry(city, f"{base_url}/app/__runtime_test.html")
    if dom.count('class="event-card') <= 0:
        raise AssertionError(f"No event cards rendered for {city}")
    if f'data-city="{city}"' not in dom:
        raise AssertionError(f"Active city context did not apply for {city}")
    for marker, message in (
        ('data-combined-workbench="true"', "Combined workbench missing"),
        ('data-combined-when="true"', "Date filter missing"),
        ('data-combined-price="true"', "Price filter missing"),
        ('data-combined-categories="true"', "Category filters missing"),
        ('data-filter-url-price="gratis"', "Price filter URL persistence failed"),
        ('data-sources-default-hidden="true"', "Sources visible by default"),
        ('data-sources-after-open="true"', "Sources did not open"),
        ('data-search-toggle-present="true"', "Search trigger missing"),
        ('data-search-initially-hidden="true"', "Search consumes space before opening"),
        ('data-search-after-open="true"', "Search did not open"),
        ('data-search-input-visible="true"', "Smart search unavailable"),
        ('data-city-title-white-space="nowrap"', "City title wraps"),
        ('data-detail-open="true"', "Event detail did not open"),
        ('data-detail-has-source="true"', "Event detail source missing"),
    ):
        if marker not in dom:
            raise AssertionError(f"{message} for {city}")
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
    if city == "gijon" and 'class="event-card-photo"' not in dom:
        raise AssertionError("Gijon official event image missing")
    if 'No te lo pierdas' not in dom:
        raise AssertionError(f"Featured badge missing for {city}")
    print(f"Browser runtime {city}: combined filters and shareable URL state OK")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
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
