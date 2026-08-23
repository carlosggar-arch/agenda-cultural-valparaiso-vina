from __future__ import annotations

import re
import tempfile
import time
import uuid

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from production_pwa_smoke import (
    ORIGINS,
    PRIMARY_ORIGIN,
    assert_loaded_dom,
    expected_shell,
    release_number,
)

READY_TIMEOUT_SECONDS = 25
CASES = (
    ("valparaiso", "Valparaíso / Viña del Mar", 390, 844),
    ("gijon", "Gijón / Xixón", 1280, 900),
)


def chrome_options(profile: str, width: int, height: int) -> Options:
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
        f"--window-size={width},{height}",
        f"--user-data-dir={profile}",
    ):
        options.add_argument(argument)
    return options


def runtime_ready(driver: webdriver.Chrome, city: str, expected_release: int) -> bool:
    return bool(
        driver.execute_script(
            """
            return document.documentElement.dataset.vivamosReady === 'true'
              && document.documentElement.dataset.city === arguments[0]
              && Number(globalThis.__VIVAMOS_RELEASE__) === arguments[1]
              && document.querySelectorAll('.event-card').length > 0;
            """,
            city,
            expected_release,
        )
    )


def load_dom(
    driver: webdriver.Chrome,
    base: str,
    city: str,
    width: int,
    height: int,
    expected_release: int,
    extra: str = "",
) -> str:
    driver.set_window_size(width, height)
    suffix = f"&{extra.lstrip('&?')}" if extra else ""
    url = f"{base}?city={city}{suffix}&smoke={uuid.uuid4().hex}"
    driver.get(url)
    WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(
        lambda current: runtime_ready(current, city, expected_release)
    )
    return driver.page_source


def cold_dom(
    origin: str,
    base: str,
    city: str,
    width: int,
    height: int,
    expected_release: int,
) -> str:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-prod-{origin}-{city}-") as profile:
            driver = webdriver.Chrome(options=chrome_options(profile, width, height))
            try:
                return load_dom(driver, base, city, width, height, expected_release)
            except Exception as exc:
                last_error = str(exc)
            finally:
                driver.quit()
        if attempt < 2:
            time.sleep(2)
    raise SystemExit(
        f"Selenium cold load failed for {origin}/{city} {width}x{height} after retry: {last_error}"
    )


def main() -> None:
    expected_release = release_number()
    expected = expected_shell()

    for origin, base in ORIGINS.items():
        for city, label, width, height in CASES:
            dom = cold_dom(origin, base, city, width, height, expected_release)
            assert_loaded_dom(
                dom,
                origin,
                city,
                label,
                width,
                height,
                expected_release,
                expected,
            )
            print(
                f"PRODUCTION_COLD_LOAD_OK origin={origin} city={city} "
                f"viewport={width}x{height} transport=selenium"
            )

    base = ORIGINS[PRIMARY_ORIGIN]
    with tempfile.TemporaryDirectory(prefix="vivamos-roundtrip-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 390, 844))
        try:
            first_valpo = load_dom(
                driver, base, "valparaiso", 390, 844, expected_release
            )
            assert_loaded_dom(
                first_valpo,
                PRIMARY_ORIGIN,
                "valparaiso",
                "Valparaíso / Viña del Mar",
                390,
                844,
                expected_release,
                expected,
            )

            gijon = load_dom(driver, base, "gijon", 1280, 900, expected_release)
            assert_loaded_dom(
                gijon,
                PRIMARY_ORIGIN,
                "gijon",
                "Gijón / Xixón",
                1280,
                900,
                expected_release,
                expected,
            )

            final_valpo = load_dom(
                driver,
                base,
                "valparaiso",
                390,
                844,
                expected_release,
                "when=7-dias",
            )
            assert_loaded_dom(
                final_valpo,
                PRIMARY_ORIGIN,
                "valparaiso",
                "Valparaíso / Viña del Mar",
                390,
                844,
                expected_release,
                expected,
            )
            if 'data-card-enhanced="true"' not in final_valpo:
                raise SystemExit(
                    "Valpo/Viña rich cards did not recover after Gijón roundtrip"
                )
            if (
                "event-card-photo" not in final_valpo
                and "event-card-media" not in final_valpo
            ):
                raise SystemExit(
                    "Valpo/Viña cards lost image/media presentation after Gijón roundtrip"
                )
            active_seven_days = re.search(
                r'<button[^>]*(?:data-filter-value="7-dias"[^>]*aria-pressed="true"|aria-pressed="true"[^>]*data-filter-value="7-dias")[^>]*>',
                final_valpo,
                flags=re.I,
            )
            if not active_seven_days:
                raise SystemExit(
                    "Roundtrip filter state did not apply after returning to Valpo/Viña"
                )
            print(
                "PRODUCTION_CITY_ROUNDTRIP_OK origin=github-pages "
                "valparaiso->gijon->valparaiso filter=7-dias transport=selenium"
            )
        finally:
            driver.quit()


if __name__ == "__main__":
    main()
