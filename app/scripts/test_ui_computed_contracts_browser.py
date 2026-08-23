from __future__ import annotations

import http.server
import json
import shutil
import socketserver
import threading
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "tests/ui-computed-contracts.json"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def chrome_options() -> webdriver.ChromeOptions:
    options = webdriver.ChromeOptions()
    binary = next(
        (shutil.which(name) for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser") if shutil.which(name)),
        None,
    )
    if binary:
        options.binary_location = binary
    for argument in (
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
    ):
        options.add_argument(argument)
    return options


def measure(driver: webdriver.Chrome, contract: dict) -> list[dict]:
    return driver.execute_script(
        """
        const contract = arguments[0];
        return [...document.querySelectorAll(contract.selector)]
          .filter((node) => {
            const rect = node.getBoundingClientRect();
            const style = getComputedStyle(node);
            return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
          })
          .slice(0, contract.sample_limit || 20)
          .map((node) => {
            const style = getComputedStyle(node, contract.pseudo || null);
            const rect = node.getBoundingClientRect();
            const computed = {};
            for (const property of Object.keys(contract.computed || {})) computed[property] = style[property];
            return {computed, rect: {width: rect.width, height: rect.height}};
          });
        """,
        contract,
    )


def assert_contract(contract: dict, context_id: str, rows: list[dict]) -> None:
    minimum = int(contract.get("min_count", 1))
    if len(rows) < minimum:
        raise AssertionError(
            f"UI_COMPUTED_CONTRACT_MISSING id={contract['id']} context={context_id} "
            f"selector={contract['selector']} expected>={minimum} actual={len(rows)}"
        )
    for index, row in enumerate(rows):
        for property_name, expected in contract.get("computed", {}).items():
            actual = row["computed"].get(property_name)
            if actual != expected:
                raise AssertionError(
                    f"UI_COMPUTED_CONTRACT_STYLE id={contract['id']} context={context_id} "
                    f"sample={index} property={property_name} expected={expected} actual={actual}"
                )
        rect_contract = contract.get("rect") or {}
        tolerance = float(rect_contract.get("tolerance", 0))
        for dimension in ("width", "height"):
            if dimension not in rect_contract:
                continue
            expected = float(rect_contract[dimension])
            actual = float(row["rect"][dimension])
            if abs(actual - expected) > tolerance:
                raise AssertionError(
                    f"UI_COMPUTED_CONTRACT_RECT id={contract['id']} context={context_id} "
                    f"sample={index} dimension={dimension} expected={expected} actual={actual} tolerance={tolerance}"
                )


def main() -> None:
    definition = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    assert definition.get("schema_version") == "1.0.0"
    contexts = definition["contexts"]
    contracts = definition["contracts"]
    assert contexts and contracts, "computed UI contract registry must not be empty"

    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with webdriver.Chrome(options=chrome_options()) as driver:
                for context_id, context in contexts.items():
                    width, height = context["viewport"]
                    driver.set_window_size(width, height)
                    driver.get(f"http://127.0.0.1:{port}/app/?city={context['city']}")
                    relevant = [row for row in contracts if context_id in row.get("contexts", [])]
                    selectors = sorted({row["selector"] for row in relevant})
                    WebDriverWait(driver, 30).until(
                        lambda browser: all(browser.find_elements("css selector", selector) for selector in selectors)
                    )
                    for contract in relevant:
                        rows = measure(driver, contract)
                        assert_contract(contract, context_id, rows)
                        print(
                            f"UI_COMPUTED_CONTRACT_OK id={contract['id']} "
                            f"context={context_id} samples={len(rows)}",
                            flush=True,
                        )
        finally:
            server.shutdown()
            thread.join(timeout=2)

    print(f"UI_COMPUTED_CONTRACTS_OK contracts={len(contracts)} contexts={len(contexts)}")


if __name__ == "__main__":
    main()
