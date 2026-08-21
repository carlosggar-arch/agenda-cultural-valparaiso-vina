from __future__ import annotations

import http.server
import json
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
TEST_PAGE = APP / "__exhibition_filter_isolation.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def make_test_page() -> None:
    # Use the real app shell; Selenium supplies the deterministic interaction and
    # waiting contract instead of injecting a virtual-time dump-dom probe.
    source = (APP / "index.html").read_text(encoding="utf-8")
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
        "--disable-extensions",
        "--disable-sync",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1360,1000",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(arg)
    return webdriver.Chrome(options=options)


VISIBLE_GROUPS_JS = r'''
const visible = (node) => {
  if (!node || node.hidden || node.closest('[hidden]')) return false;
  const style = getComputedStyle(node);
  return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
};
return [...document.querySelectorAll('[data-unified-exhibition-group="true"]')].filter(visible).length;
'''


def visible_groups(driver) -> int:
    return int(driver.execute_script(VISIBLE_GROUPS_JS) or 0)


def chip_state(driver, category_id: str) -> str | None:
    return driver.execute_script(
        "const b=[...document.querySelectorAll('[data-combined-category]')].find(x=>x.dataset.combinedCategory===arguments[0]); return b?.getAttribute('aria-pressed') ?? null;",
        category_id,
    )


def click_chip(driver, category_id: str) -> bool:
    return bool(driver.execute_script(
        "const b=[...document.querySelectorAll('[data-combined-category]')].find(x=>x.dataset.combinedCategory===arguments[0]); if(!b) return false; b.click(); return true;",
        category_id,
    ))


def non_exhibition_category(driver) -> str | None:
    return driver.execute_script(r'''
      const button = [...document.querySelectorAll('[data-combined-category]')]
        .find((candidate) => candidate.dataset.combinedCategory !== 'exposiciones'
          && Number(candidate.querySelector('small')?.textContent || 0) > 0);
      return button?.dataset.combinedCategory || null;
    ''')


def run_browser(url: str) -> dict[str, str]:
    last_error = ""
    for attempt in range(2):
        with tempfile.TemporaryDirectory(prefix="vivamos-exhibition-filter-", ignore_cleanup_errors=True) as profile:
            driver = None
            try:
                driver = new_driver(profile)
                wait = WebDriverWait(driver, 25, poll_frequency=0.05)
                driver.get(url)

                wait.until(lambda current: visible_groups(current) > 0)
                non_id = wait.until(lambda current: non_exhibition_category(current))
                if not click_chip(driver, non_id):
                    raise AssertionError(f"could not click non-exhibition category {non_id}")

                wait.until(lambda current: chip_state(current, non_id) == "true")
                wait.until(lambda current: visible_groups(current) == 0)
                non_groups = visible_groups(driver)
                non_active = chip_state(driver, non_id) == "true"

                if not click_chip(driver, non_id):
                    raise AssertionError(f"could not clear non-exhibition category {non_id}")
                wait.until(lambda current: chip_state(current, non_id) != "true")
                wait.until(lambda current: chip_state(current, "exposiciones") is not None)
                if not click_chip(driver, "exposiciones"):
                    raise AssertionError("could not click Exposiciones category")

                wait.until(lambda current: chip_state(current, "exposiciones") == "true")
                wait.until(lambda current: visible_groups(current) > 0)
                expo_groups = visible_groups(driver)
                expo_active = chip_state(driver, "exposiciones") == "true"

                return {
                    "ready": "true",
                    "non_category": str(non_id),
                    "non_active": "true" if non_active else "false",
                    "groups_under_non": str(non_groups),
                    "expo_active": "true" if expo_active else "false",
                    "groups_under_expo": str(expo_groups),
                    "error": "(absent)",
                }
            except Exception as exc:
                last_error = f"attempt {attempt + 1}: {type(exc).__name__}: {exc}"
            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass
    return {
        "ready": "error",
        "non_category": "(unknown)",
        "non_active": "false",
        "groups_under_non": "(unknown)",
        "expo_active": "false",
        "groups_under_expo": "(unknown)",
        "error": last_error or "browser probe failed",
    }


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
                diagnostics = run_browser(f"http://127.0.0.1:{port}/app/{TEST_PAGE.name}?city=gijon&when=todos")
            finally:
                server.shutdown()
                thread.join(timeout=2)
    finally:
        TEST_PAGE.unlink(missing_ok=True)

    print("EXHIBITION_FILTER_ISOLATION_DIAGNOSTICS " + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    assert diagnostics["ready"] == "true", f"filter isolation probe did not finish: {diagnostics}"
    assert diagnostics["non_active"] == "true", f"non-exhibition category did not become active: {diagnostics}"
    assert diagnostics["groups_under_non"] == "0", (
        "grouped exhibitions must be hidden when a non-exhibition category is selected; "
        f"diagnostics={diagnostics}"
    )
    assert diagnostics["expo_active"] == "true", f"Exposiciones category did not become active: {diagnostics}"
    assert int(diagnostics["groups_under_expo"]) > 0, f"grouped exhibitions must reappear under Exposiciones: {diagnostics}"
    print("Exhibition category isolation browser contract: OK")


if __name__ == "__main__":
    main()
