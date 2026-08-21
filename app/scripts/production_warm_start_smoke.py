from __future__ import annotations

import tempfile
import time
import uuid

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from production_pwa_smoke import ORIGINS, release_number

MOBILE_CITY = "valparaiso"
MOBILE_WIDTH = 390
MOBILE_HEIGHT = 844
CACHE_MARKER_KEY = "vivamos-processed-pipeline-marker-valparaiso"
READY_TIMEOUT_SECONDS = 20
CACHE_WRITE_TIMEOUT_SECONDS = 8
MAX_WARM_RATIO = 1.75
MAX_WARM_EXTRA_SECONDS = 4.0


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
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication",
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={MOBILE_WIDTH},{MOBILE_HEIGHT}",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(argument)
    return options


def core_is_ready(driver: webdriver.Chrome, expected_release: int) -> bool:
    return bool(driver.execute_script(
        """
        return document.documentElement.dataset.vivamosReady === 'true'
          && document.documentElement.dataset.city === arguments[0]
          && Number(globalThis.__VIVAMOS_RELEASE__) === arguments[1]
          && document.querySelectorAll('.event-card').length > 0;
        """,
        MOBILE_CITY,
        expected_release,
    ))


def timed_core_load(driver: webdriver.Chrome, base: str, expected_release: int) -> float:
    url = f"{base}?city={MOBILE_CITY}&warmprobe={uuid.uuid4().hex}"
    started = time.monotonic()
    driver.get(url)
    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
        lambda current: core_is_ready(current, expected_release)
    )
    return time.monotonic() - started


def wait_for_processed_cache(driver: webdriver.Chrome) -> None:
    WebDriverWait(driver, CACHE_WRITE_TIMEOUT_SECONDS, poll_frequency=0.05).until(
        lambda current: bool(current.execute_script(
            "return localStorage.getItem(arguments[0]);",
            CACHE_MARKER_KEY,
        ))
    )


def main() -> None:
    expected_release = release_number()

    for origin, base in ORIGINS.items():
        with tempfile.TemporaryDirectory(prefix=f"vivamos-warm-{origin}-") as profile:
            driver = webdriver.Chrome(options=chrome_options(profile))
            try:
                cold_seconds = timed_core_load(driver, base, expected_release)
                wait_for_processed_cache(driver)
                driver.get("about:blank")
                warm_seconds = timed_core_load(driver, base, expected_release)
            finally:
                driver.quit()

            warm_limit = max(
                cold_seconds * MAX_WARM_RATIO,
                cold_seconds + MAX_WARM_EXTRA_SECONDS,
            )
            if warm_seconds > warm_limit:
                raise SystemExit(
                    "Warm mobile reopen regressed: "
                    f"origin={origin} cold={cold_seconds:.2f}s warm={warm_seconds:.2f}s "
                    f"limit={warm_limit:.2f}s"
                )

            ratio = cold_seconds / warm_seconds if warm_seconds > 0 else float("inf")
            print(
                "PRODUCTION_WARM_REOPEN_OK "
                f"origin={origin} release=v{expected_release} viewport={MOBILE_WIDTH}x{MOBILE_HEIGHT} "
                f"cold={cold_seconds:.2f}s warm={warm_seconds:.2f}s speedup={ratio:.2f}x "
                "processed_cache=ready"
            )


if __name__ == "__main__":
    main()
