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
        raise AssertionError("app.js/combined-filters.js/pwa.js script marker not found in app/index.html")

    # The runtime contract deliberately avoids service-worker registration while
    # loading the same presentation/filter modules as pwa.js. Remove the normal
    # combined-filter entry point first so it is not executed twice.
    source = source.replace(combined_marker, "", 1).replace(pwa_marker, "", 1)

    diagnostic = r'''
  <script>
    setTimeout(() => {
      const sourceSection = document.querySelector("[data-sources-section]");
      const sourceToggle = document.querySelector("[data-sources-toggle]");
      document.body.dataset.gijonVisualReference = document.querySelector("[data-gijon-visual-reference]") ? "true" : "false";
      document.body.dataset.sourcesDefaultHidden = sourceSection && getComputedStyle(sourceSection).display === "none" ? "true" : "false";
      if (sourceToggle) sourceToggle.click();
      document.body.dataset.sourcesAfterOpen = sourceSection && getComputedStyle(sourceSection).display !== "none" ? "true" : "false";

      const cityTitle = document.querySelector("[data-header-city-title]");
      const searchToggle = document.querySelector("[data-header-search-toggle]");
      const searchPopover = document.querySelector("[data-header-search-popover]");
      document.body.dataset.cityTitle = cityTitle?.textContent || "";
      document.body.dataset.cityTitleWhiteSpace = cityTitle ? getComputedStyle(cityTitle).whiteSpace : "";
      document.body.dataset.searchTogglePresent = searchToggle ? "true" : "false";
      document.body.dataset.searchInitiallyHidden = searchPopover?.hidden ? "true" : "false";
      if (searchToggle) searchToggle.click();
      document.body.dataset.searchAfterOpen = searchPopover && !searchPopover.hidden ? "true" : "false";
      document.body.dataset.searchInputVisible = document.querySelector("[data-smart-search]") && searchPopover && !searchPopover.hidden ? "true" : "false";

      const workbench = document.querySelector(".filter-workbench");
      const when = document.querySelector("[data-combined-when]");
      const price = document.querySelector("[data-combined-price]");
      const areaGroup = document.querySelector("[data-area-filter-group]");
      const categoryButtons = [...document.querySelectorAll("[data-combined-category]")];
      document.body.dataset.combinedWorkbench = workbench ? "true" : "false";
      document.body.dataset.combinedWhen = when ? "true" : "false";
      document.body.dataset.combinedPrice = price ? "true" : "false";
      document.body.dataset.combinedCategories = categoryButtons.length > 0 ? "true" : "false";
      document.body.dataset.areaFilterHidden = areaGroup && getComputedStyle(areaGroup).display === "none" ? "true" : "false";

      // Exercise two dimensions together in Valpo and one dimension in Gijón;
      // the URL is the public persistence contract for shareable filtered views.
      const city = document.documentElement.dataset.city;
      if (city === "valparaiso") {
        document.querySelector('[data-combined-area] [data-filter-value="valparaiso"]')?.click();
        document.querySelector('[data-combined-price] [data-filter-value="gratis"]')?.click();
      } else {
        document.querySelector('[data-combined-price] [data-filter-value="gratis"]')?.click();
      }

      setTimeout(() => {
        const params = new URLSearchParams(location.search);
        document.body.dataset.filterUrlPrice = params.get("price") || "";
        document.body.dataset.filterUrlArea = params.get("area") || "";
        const visibleCards = [...document.querySelectorAll(".event-card[data-event-id]")].filter((card) => !card.hidden);
        document.body.dataset.visibleFilteredCards = String(visibleCards.length);

        const trigger = document.querySelector("[data-open-event]");
        if (trigger) trigger.click();
        const detail = document.querySelector("dialog[data-event-detail]");
        document.body.dataset.detailOpen = detail && detail.hasAttribute("open") ? "true" : "false";
        document.body.dataset.detailHasSource = detail && detail.textContent.includes("Fuente oficial") ? "true" : "false";
      }, 500);
    }, 5500);
  </script>'''

    injection = (
        f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>\n  '
        + app_marker
        + '\n  <script type="module" src="./combined-filters.js"></script>'
        + '\n  <script type="module" src="./card-experience.js"></script>'
        + '\n  <script type="module" src="./schedule-display.js"></script>'
        + '\n  <script type="module" src="./card-image-fallback.js"></script>'
        + '\n  <script type="module" src="./compact-top.js"></script>'
        + '\n  <script type="module" src="./gijon-visual-reference.js"></script>'
        + '\n  <script type="module" src="./sources-toggle.js"></script>'
        + '\n  <script type="module" src="./header-redesign.js"></script>'
        + '\n  <script type="module" src="./density-polish.js"></script>'
        + '\n  <script type="module" src="./combined-filters-polish.js"></script>'
        + diagnostic
    )
    TEST_PAGE.write_text(source.replace(app_marker, injection, 1), encoding="utf-8")


def run_city(city: str, base_url: str) -> None:
    make_test_page(city)
    with tempfile.TemporaryDirectory(prefix=f"agenda-{city}-chrome-", ignore_cleanup_errors=True) as profile:
        cmd = [
            chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-background-networking",
            "--virtual-time-budget=8500", f"--user-data-dir={profile}", "--dump-dom",
            f"{base_url}/app/__runtime_test.html",
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=45)
        if result.returncode != 0:
            raise AssertionError(f"Chrome failed for {city}: exit={result.returncode}\nSTDERR:\n{result.stderr[-4000:]}")
        dom = result.stdout
        card_count = dom.count('class="event-card')
        if card_count <= 0:
            raise AssertionError(f"No event cards rendered for {city}. DOM tail:\n{dom[-5000:]}")
        if f'data-city="{city}"' not in dom:
            raise AssertionError(f"Active city context did not apply for {city}")

        for marker, message in (
            ('data-combined-workbench="true"', "Combined filter workbench did not render"),
            ('data-combined-when="true"', "Combined date controls did not render"),
            ('data-combined-price="true"', "Combined price controls did not render"),
            ('data-combined-categories="true"', "Contextual multi-category controls did not render"),
            ('data-filter-url-price="gratis"', "Price filter was not persisted to the URL"),
            ('data-sources-default-hidden="true"', "Agenda sources are visible without explicit user action"),
            ('data-sources-after-open="true"', "Agenda sources did not open after explicit user action"),
            ('data-search-toggle-present="true"', "Compact search trigger did not render"),
            ('data-search-initially-hidden="true"', "Search field consumes space before explicit user action"),
            ('data-search-after-open="true"', "Compact search trigger did not open the floating field"),
            ('data-search-input-visible="true"', "Smart search input was not available after opening search"),
            ('data-city-title-white-space="nowrap"', "City title is allowed to wrap"),
            ('data-detail-open="true"', "Internal event detail did not open"),
            ('data-detail-has-source="true"', "Internal event detail did not expose source"),
        ):
            if marker not in dom:
                raise AssertionError(f"{message} for {city}")

        expected_title = "Valparaíso / Viña del Mar" if city == "valparaiso" else "Gijón / Xixón"
        if f'data-city-title="{expected_title}"' not in dom:
            raise AssertionError(f"Unexpected one-line city title for {city}")
        if city == "valparaiso":
            if 'data-filter-url-area="valparaiso"' not in dom:
                raise AssertionError("Valparaiso sub-area filter was not persisted")
            if 'data-area-filter-hidden="false"' not in dom:
                raise AssertionError("Valparaiso/Viña area filter should be visible in Valparaiso mode")
        else:
            if 'data-area-filter-hidden="true"' not in dom:
                raise AssertionError("Valparaiso/Viña area filter leaked into Gijon mode")
            if 'data-filter-url-area=""' not in dom:
                raise AssertionError("Gijon URL should not retain a Valparaiso sub-area filter")

        if 'class="event-card-source"' not in dom or 'class="source-card"' not in dom:
            raise AssertionError(f"Source data did not remain available for {city}")
        if city == "gijon":
            if 'data-gijon-visual-reference="true"' not in dom or "https://www.gijon.es/app/actividades/oferta" not in dom:
                raise AssertionError("Gijon official visual activity reference did not render")
        elif 'data-gijon-visual-reference="true"' in dom:
            raise AssertionError("Gijon visual reference leaked into Valparaiso")
        if city == "valparaiso" and 'data-image-kind="category-fallback"' not in dom:
            raise AssertionError("Valparaiso should replace missing images with category photos")
        if city == "gijon" and 'class="event-card-photo"' not in dom:
            raise AssertionError("Gijon should expose at least one official event image")
        if 'No te lo pierdas' not in dom:
            raise AssertionError(f"Featured editorial badge did not render for {city}")
        print(f"Browser runtime {city}: {card_count} rich cards rendered with combined filters and shareable URL state")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            for city in ("valparaiso", "gijon"):
                run_city(city, f"http://127.0.0.1:{port}")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
