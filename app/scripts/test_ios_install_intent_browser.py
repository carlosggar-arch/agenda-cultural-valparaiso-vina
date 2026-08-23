from __future__ import annotations

import http.server
import socketserver
import tempfile
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
)
VIEWPORT = (390, 844)
WAIT_SECONDS = 20


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def chrome_options(profile: str) -> Options:
    options = Options()
    options.page_load_strategy = "eager"
    for argument in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-sync",
        "--disable-background-networking",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={VIEWPORT[0]},{VIEWPORT[1]}",
        f"--user-agent={IPHONE_UA}",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(argument)
    return options


def static_metadata(driver: webdriver.Chrome) -> dict[str, str | bool]:
    return driver.execute_script(
        """
        const value = (name) => document.head.querySelector(`meta[name="${name}"]`)?.content || '';
        return {
          applicationName: value('application-name'),
          mobileCapable: value('mobile-web-app-capable'),
          appleCapable: value('apple-mobile-web-app-capable'),
          appleTitle: value('apple-mobile-web-app-title'),
          appleStatus: value('apple-mobile-web-app-status-bar-style'),
          appleIcon: document.head.querySelector('link[rel="apple-touch-icon"]')?.getAttribute('href') || '',
          mobileMetaBeforeOptionalUi: Boolean(document.head.querySelector('meta[name="apple-mobile-web-app-capable"]')),
        };
        """
    )


def assert_metadata(driver: webdriver.Chrome) -> None:
    metadata = static_metadata(driver)
    assert metadata["applicationName"] == "¡Vivamos!"
    assert metadata["mobileCapable"] == "yes"
    assert metadata["appleCapable"] == "yes"
    assert metadata["appleTitle"] == "¡Vivamos!"
    assert metadata["appleStatus"] == "default"
    assert str(metadata["appleIcon"]).endswith("./icons/icon-192.png")
    assert metadata["mobileMetaBeforeOptionalUi"] is True


def install_help_visible(driver: webdriver.Chrome) -> bool:
    return bool(
        driver.execute_script(
            """
            const backdrop = document.querySelector('[data-install-help-backdrop]');
            return Boolean(backdrop && !backdrop.hidden);
            """
        )
    )


def run_intent_case(base: str) -> None:
    with tempfile.TemporaryDirectory(prefix="vivamos-ios-intent-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile))
        try:
            driver.get(f"{base}?city=valparaiso&install=1")
            assert_metadata(driver)
            WebDriverWait(driver, WAIT_SECONDS, poll_frequency=0.05).until(install_help_visible)
            heading = driver.execute_script(
                "return document.querySelector('#install-help-title')?.textContent?.trim() || '';"
            )
            copy = driver.execute_script(
                "return document.querySelector('[data-install-help-backdrop]')?.textContent || '';"
            )
            chooser_visible = driver.execute_script(
                """
                const chooser = document.querySelector('[data-chooser-backdrop]');
                return Boolean(chooser && !chooser.hidden);
                """
            )
            assert heading == "Añádela a tu iPhone"
            assert "Solo necesitas hacerlo una vez" in copy
            assert "Compartir" in copy
            assert "Añadir a pantalla de inicio" in copy
            assert "Abrir como app" in copy
            assert copy.index("Compartir") < copy.index("Añadir a pantalla de inicio")
            assert copy.index("Añadir a pantalla de inicio") < copy.index("Abrir como app")
            assert len(driver.find_elements("css selector", ".install-help-steps li")) == 4
            assert driver.switch_to.active_element.get_attribute("data-install-help-close") == ""
            assert chooser_visible is False, "install-intent help must not overlap the city chooser"
        finally:
            driver.quit()


def run_regular_case(base: str) -> None:
    with tempfile.TemporaryDirectory(prefix="vivamos-ios-regular-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile))
        try:
            driver.get(f"{base}?city=valparaiso")
            assert_metadata(driver)
            WebDriverWait(driver, WAIT_SECONDS, poll_frequency=0.05).until(
                lambda current: current.execute_script(
                    "return document.documentElement.dataset.vivamosReady === 'true';"
                )
            )
            assert install_help_visible(driver) is False, "normal iPhone visits must not auto-open install help"
        finally:
            driver.quit()


def main() -> None:
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}/app/"
            run_intent_case(base)
            run_regular_case(base)
        finally:
            server.shutdown()
            thread.join(timeout=2)

    print("IOS_INSTALL_INTENT_BROWSER_OK intent=guided regular=unobtrusive metadata=static")


if __name__ == "__main__":
    main()
