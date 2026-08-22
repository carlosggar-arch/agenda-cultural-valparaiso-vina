from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import tempfile
import threading
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

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


def make_test_page(city: str | None = None) -> None:
    """Copy the real app shell, optionally pre-seeding a city for legacy probes.

    D3's canonical runtime scenario uses the real query-param city contract. The
    optional localStorage bootstrap is retained for older diagnostics that import
    this helper, without re-declaring any presentation modules.
    """
    source = (APP / "index.html").read_text(encoding="utf-8")
    if city:
        release_marker = '<script src="./release-version.js"></script>'
        bootstrap = f'<script>localStorage.setItem("agenda-cultural-city", "{city}");</script>'
        if release_marker not in source:
            raise AssertionError("release-version.js marker not found in app shell")
        source = source.replace(release_marker, release_marker + "\n  " + bootstrap, 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def new_driver(profile: str):
    options = Options()
    options.binary_location = chrome_binary()
    options.page_load_strategy = "none"
    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1360,1000",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(arg)
    return webdriver.Chrome(options=options)


VISIBLE_COUNT_JS = r'''
const visible = (node) => {
  if (!node || node.hidden || node.closest('[hidden]')) return false;
  const style = getComputedStyle(node);
  return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
};
return [...document.querySelectorAll('.event-card[data-event-id]')].filter(visible).length;
'''


def visible_cards(driver) -> int:
    return int(driver.execute_script(VISIBLE_COUNT_JS) or 0)


def click_js(driver, selector: str) -> bool:
    return bool(driver.execute_script(
        "const node=document.querySelector(arguments[0]); if(!node) return false; node.click(); return true;",
        selector,
    ))


def is_visible(driver, selector: str) -> bool:
    return bool(driver.execute_script(r'''
      const node = document.querySelector(arguments[0]);
      if (!node || node.hidden || node.closest('[hidden]')) return false;
      const style = getComputedStyle(node);
      return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
    ''', selector))


def choose_date_filter(driver, initial_count: int) -> str | None:
    return driver.execute_script(r'''
      const buttons = [...document.querySelectorAll('[data-combined-when] [data-filter-value]')]
        .filter((button) => !['todos', 'personalizado'].includes(button.dataset.filterValue));
      const chosen = buttons.find((button) => {
        const count = Number(button.querySelector('[data-combined-count]')?.textContent || -1);
        return Number.isFinite(count) && count >= 0 && count !== arguments[0];
      }) || buttons.find((button) => button.dataset.filterValue === '7-dias') || buttons[0];
      if (!chosen) return null;
      chosen.click();
      return chosen.dataset.filterValue || null;
    ''', initial_count)


def run_city(city: str, base_url: str) -> dict[str, str | int | bool]:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-runtime-{city}-{attempt}-", ignore_cleanup_errors=True) as profile:
            driver = None
            try:
                driver = new_driver(profile)
                wait = WebDriverWait(driver, 30, poll_frequency=0.1)
                driver.get(f"{base_url}/app/{TEST_PAGE.name}?city={city}&when=todos")

                wait.until(lambda current: current.execute_script(
                    "return document.documentElement.dataset.city === arguments[0]", city
                ))
                wait.until(lambda current: visible_cards(current) > 0)
                initial_count = visible_cards(driver)

                expected_title = "Valparaíso / Viña del Mar" if city == "valparaiso" else "Gijón / Xixón"
                wait.until(lambda current: current.execute_script(
                    "return document.querySelector('[data-header-city-title]')?.textContent?.trim() === arguments[0]",
                    expected_title,
                ))

                if not click_js(driver, "[data-header-search-toggle]"):
                    raise AssertionError("search trigger missing")
                wait.until(lambda current: is_visible(current, "[data-header-search-popover]"))
                if not is_visible(driver, "[data-smart-search]"):
                    raise AssertionError("smart search input unavailable after opening search")

                source_section = "[data-sources-section]"
                if is_visible(driver, source_section):
                    raise AssertionError("sources section must start collapsed")
                if not click_js(driver, "[data-sources-toggle]"):
                    raise AssertionError("sources toggle missing")
                wait.until(lambda current: is_visible(current, source_section))
                if not driver.find_elements("css selector", ".source-card"):
                    raise AssertionError("source cards unavailable after opening sources")

                selected_when = choose_date_filter(driver, initial_count)
                if not selected_when:
                    raise AssertionError("no usable date filter found")
                wait.until(lambda current: current.execute_script(
                    "return new URL(location.href).searchParams.get('when') === arguments[0]", selected_when
                ))
                wait.until(lambda current: visible_cards(current) != initial_count)
                filtered_count = visible_cards(driver)
                if filtered_count <= 0:
                    raise AssertionError(f"date filter {selected_when} left no visible cards")

                if city == "valparaiso":
                    if not is_visible(driver, "[data-area-filter-group]"):
                        raise AssertionError("Valparaiso area filters are not visible")
                    if not click_js(driver, '[data-combined-area] [data-filter-value="valparaiso"]'):
                        raise AssertionError("Valparaiso area option unavailable")
                    wait.until(lambda current: current.execute_script(
                        "return new URL(location.href).searchParams.get('area') === 'valparaiso'"
                    ))
                elif is_visible(driver, "[data-area-filter-group]"):
                    raise AssertionError("Gijon must not expose Valparaiso/Viña area filters")

                opened = bool(driver.execute_script(r'''
                  const visible = (node) => {
                    if (!node || node.hidden || node.closest('[hidden]')) return false;
                    const style = getComputedStyle(node);
                    return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
                  };
                  const trigger = [...document.querySelectorAll('[data-open-event]')].find(visible);
                  if (!trigger) return false;
                  trigger.click();
                  return true;
                '''))
                if not opened:
                    raise AssertionError("no visible event detail trigger after filtering")

                wait.until(lambda current: current.execute_script(
                    "return Boolean(document.querySelector('dialog[data-event-detail][open]'))"
                ))
                detail = driver.execute_script(r'''
                  const dialog = document.querySelector('dialog[data-event-detail][open]');
                  if (!dialog) return null;
                  const sourceAction = [...dialog.querySelectorAll('a.event-detail-action[href]')]
                    .find((link) => /fuente|open data/i.test(link.textContent || ''));
                  return {
                    source: Boolean(sourceAction),
                    sourceHref: sourceAction?.href || '',
                    provenance: Boolean(dialog.querySelector('.event-detail-provenance')),
                    media: Boolean(dialog.querySelector('img, picture, .event-detail-media')),
                    actions: dialog.querySelectorAll('.event-detail-action').length,
                  };
                ''')
                if not detail or not detail["source"] or not str(detail["sourceHref"]).startswith(("http://", "https://")):
                    raise AssertionError("event detail does not expose canonical safe source evidence action")
                if not detail["media"]:
                    raise AssertionError("event detail does not expose canonical media")

                return {
                    "city": city,
                    "initial": initial_count,
                    "filtered": filtered_count,
                    "when": selected_when,
                    "detail_actions": int(detail["actions"]),
                    "source_provenance": bool(detail["provenance"]),
                }
            except Exception as exc:
                last_error = f"attempt {attempt}: {type(exc).__name__}: {exc}"
            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
    raise AssertionError(f"runtime user-flow failed for {city}: {last_error}")


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            time.sleep(0.2)
            try:
                base_url = f"http://127.0.0.1:{port}"
                results = [run_city(city, base_url) for city in ("valparaiso", "gijon")]
            finally:
                server.shutdown()
                thread.join(timeout=2)
    finally:
        TEST_PAGE.unlink(missing_ok=True)

    for result in results:
        print(
            "RUNTIME_USER_FLOW_OK "
            f"city={result['city']} initial={result['initial']} filtered={result['filtered']} "
            f"when={result['when']} detail_actions={result['detail_actions']} "
            f"source_provenance={str(result['source_provenance']).lower()}"
        )


if __name__ == "__main__":
    main()
