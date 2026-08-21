from __future__ import annotations

import tempfile
import uuid

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from production_pwa_smoke import ORIGINS, release_number

EXPECTED_RELEASE = release_number()
CASES = (
    ("valparaiso", "Valparaíso / Viña del Mar", 390, 844),
    ("gijon", "Gijón / Xixón", 1280, 900),
)

errors: list[str] = []

for origin, base in ORIGINS.items():
    for city, label, width, height in CASES:
        with tempfile.TemporaryDirectory(prefix=f"vivamos-selenium-{origin}-{city}-") as profile:
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-extensions")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument(f"--window-size={width},{height}")
            options.add_argument(f"--user-data-dir={profile}")

            driver = webdriver.Chrome(options=options)
            try:
                url = f"{base}?city={city}&smoke={uuid.uuid4().hex}"
                driver.get(url)
                wait = WebDriverWait(driver, 45)
                wait.until(lambda d: d.execute_script(
                    "return document.documentElement.dataset.vivamosReady === 'true'"
                ))
                wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, ".event-card")) > 0)
                wait.until(lambda d: len(d.find_elements(
                    By.CSS_SELECTOR, "[data-sources-toggle], [data-sources-fallback]"
                )) > 0)

                release_global = driver.execute_script("return window.__VIVAMOS_RELEASE__")
                city_applied = driver.execute_script("return document.documentElement.dataset.city || ''")
                ready = driver.execute_script("return document.documentElement.dataset.vivamosReady || ''")
                safe_mode = driver.execute_script("return document.documentElement.dataset.vivamosSafeMode || ''")

                version = driver.find_element(By.CSS_SELECTOR, "[data-app-version]").text.strip()
                city_title = driver.find_element(By.CSS_SELECTOR, "[data-header-city-title]").text.strip()
                agenda = driver.find_element(By.CSS_SELECTOR, "[data-agenda]")
                status = driver.find_element(By.CSS_SELECTOR, "[data-status]")
                cards = driver.find_elements(By.CSS_SELECTOR, ".event-card")
                visible_cards = sum(1 for card in cards if card.is_displayed())
                source_controls = driver.find_elements(
                    By.CSS_SELECTOR, "[data-sources-toggle], [data-sources-fallback]"
                )
                visible_sources = sum(1 for node in source_controls if node.is_displayed())
                stuck_loading = status.is_displayed() and "Preparando la agenda" in status.text

                print(
                    "SELENIUM_FUNCTIONAL_PROBE "
                    f"origin={origin} city={city} release_global={release_global!r} "
                    f"version={version!r} city_applied={city_applied!r} city_title={city_title!r} "
                    f"ready={ready!r} safe_mode={safe_mode!r} agenda_visible={agenda.is_displayed()} "
                    f"cards={len(cards)} visible_cards={visible_cards} "
                    f"sources={len(source_controls)} visible_sources={visible_sources} "
                    f"stuck_loading={stuck_loading}"
                )

                if release_global != EXPECTED_RELEASE:
                    errors.append(f"{origin}/{city}: global release {release_global!r}, expected {EXPECTED_RELEASE}")
                if version != f"PWA v{EXPECTED_RELEASE}":
                    errors.append(f"{origin}/{city}: visible version {version!r}, expected PWA v{EXPECTED_RELEASE}")
                if city_applied != city:
                    errors.append(f"{origin}/{city}: city dataset is {city_applied!r}")
                if city_title != label:
                    errors.append(f"{origin}/{city}: city title {city_title!r}, expected {label!r}")
                if ready != "true":
                    errors.append(f"{origin}/{city}: vivamosReady={ready!r}")
                if safe_mode == "active":
                    errors.append(f"{origin}/{city}: safe mode active")
                if not agenda.is_displayed():
                    errors.append(f"{origin}/{city}: agenda not visible")
                if visible_cards <= 0:
                    errors.append(f"{origin}/{city}: no visible event cards")
                if visible_sources <= 0:
                    errors.append(f"{origin}/{city}: no visible source control")
                if stuck_loading:
                    errors.append(f"{origin}/{city}: still showing loading state")
            except Exception as exc:
                errors.append(f"{origin}/{city}: Selenium probe failed: {exc}")
                print(f"SELENIUM_FUNCTIONAL_PROBE_FAIL origin={origin} city={city} error={exc!r}")
            finally:
                driver.quit()

if errors:
    print("SELENIUM_FUNCTIONAL_PROBE_ERRORS")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print(f"SELENIUM_FUNCTIONAL_PROBE_OK release=v{EXPECTED_RELEASE} cases={len(ORIGINS) * len(CASES)}")
