from __future__ import annotations

import argparse
import json
import tempfile
import uuid

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from production_browser_selenium_smoke import READY_TIMEOUT_SECONDS, chrome_options, runtime_ready
from production_pwa_smoke import ORIGINS, ROOT, release_number
from production_title_identity import IDENTITY_CONTRACT, evaluate_title_contract

CONTRACT_PATH = ROOT / "app/data/production-series-contracts.json"


def load_contracts() -> list[dict[str, object]]:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0.0":
        raise SystemExit("PRODUCTION_SERIES_CONTRACT_SCHEMA_INVALID")
    contracts = payload.get("contracts") or []
    if not contracts:
        raise SystemExit("PRODUCTION_SERIES_CONTRACTS_EMPTY")
    return [row for row in contracts if isinstance(row, dict)]


def rendered_titles(driver: webdriver.Chrome) -> list[str]:
    return driver.execute_script("return [...document.querySelectorAll('.event-card h4')].map((node) => String(node.textContent || '').trim()).filter(Boolean);")


def verify_contract(origin: str, base: str, contract: dict[str, object], expected_release: int) -> None:
    city = str(contract.get("city") or "")
    section = str(contract.get("section") or "todos")
    contract_id = str(contract.get("id") or "unnamed")
    with tempfile.TemporaryDirectory(prefix=f"vivamos-series-{origin}-{city}-") as profile:
        driver = webdriver.Chrome(options=chrome_options(profile, 1280, 900))
        try:
            driver.get(f"{base}?city={city}&when={section}&series_contract={uuid.uuid4().hex}")
            WebDriverWait(driver, READY_TIMEOUT_SECONDS, poll_frequency=0.05).until(lambda current: runtime_ready(current, city, expected_release))
            titles = rendered_titles(driver)
        finally:
            driver.quit()

    result = evaluate_title_contract(
        titles,
        expected_titles=contract.get("expected_titles") or [],
        preserved_titles=contract.get("preserved_titles") or [],
        forbidden_titles=contract.get("forbidden_exact_titles") or [],
    )
    failures = {key: values for key, values in result.items() if values}
    if failures:
        raise SystemExit(
            f"PRODUCTION_SERIES_CONTRACT_FAILED origin={origin} contract={contract_id} "
            f"title_identity={IDENTITY_CONTRACT} failures={failures}"
        )
    print(
        f"PRODUCTION_SERIES_CONTRACT_OK origin={origin} contract={contract_id} city={city} section={section} "
        f"expected={len(contract.get('expected_titles') or [])} preserved={len(contract.get('preserved_titles') or [])} "
        f"title_identity={IDENTITY_CONTRACT} cardinality=one-to-one"
    )


def main() -> None:
    argparse.ArgumentParser(description="Verify data-driven event-series publication contracts on every production origin.").parse_args()
    expected_release = release_number()
    contracts = load_contracts()
    for origin, base in ORIGINS.items():
        for contract in contracts:
            verify_contract(origin, base, contract, expected_release)
    print(f"PRODUCTION_SERIES_CONTRACTS_VERIFIED contracts={len(contracts)} origins={len(ORIGINS)} title_identity={IDENTITY_CONTRACT}")


if __name__ == "__main__":
    main()
