from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("production_browser_selenium_smoke.py")


class FakeTimeout(Exception):
    pass


def load_smoke_module():
    selenium = types.ModuleType("selenium")
    webdriver = types.ModuleType("selenium.webdriver")
    selenium.webdriver = webdriver
    common = types.ModuleType("selenium.common")
    exceptions = types.ModuleType("selenium.common.exceptions")
    exceptions.TimeoutException = FakeTimeout
    chrome = types.ModuleType("selenium.webdriver.chrome")
    options = types.ModuleType("selenium.webdriver.chrome.options")
    options.Options = object
    support = types.ModuleType("selenium.webdriver.support")
    ui = types.ModuleType("selenium.webdriver.support.ui")
    ui.WebDriverWait = object
    stubs = {
        "selenium": selenium,
        "selenium.webdriver": webdriver,
        "selenium.common": common,
        "selenium.common.exceptions": exceptions,
        "selenium.webdriver.chrome": chrome,
        "selenium.webdriver.chrome.options": options,
        "selenium.webdriver.support": support,
        "selenium.webdriver.support.ui": ui,
    }
    spec = importlib.util.spec_from_file_location("production_browser_retry_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load browser smoke module")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class ProductionProbeRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_smoke_module()

    def test_transient_declared_failure_is_retried_once(self) -> None:
        calls = []

        def load(*_args) -> str:
            calls.append("call")
            if len(calls) == 1:
                raise FakeTimeout("transient")
            return "ready"

        with patch.object(self.module, "load_dom", side_effect=load), patch.object(
            self.module.time, "sleep", return_value=None
        ):
            result = self.module.load_roundtrip_dom(
                object(), "https://example.invalid/", "valparaiso", 390, 844, 253
            )

        self.assertEqual(result, "ready")
        self.assertEqual(len(calls), 2)

    def test_persistent_declared_failure_remains_terminal(self) -> None:
        calls = []

        def load(*_args) -> None:
            calls.append("call")
            raise FakeTimeout("persistent")

        with patch.object(self.module, "load_dom", side_effect=load), patch.object(
            self.module.time, "sleep", return_value=None
        ), self.assertRaisesRegex(FakeTimeout, "persistent"):
            self.module.load_roundtrip_dom(
                object(), "https://example.invalid/", "valparaiso", 390, 844, 253
            )
        self.assertEqual(len(calls), 2)

    def test_undeclared_failure_is_not_retried(self) -> None:
        calls = []

        def load(*_args) -> None:
            calls.append("call")
            raise RuntimeError("not transient")

        with patch.object(self.module, "load_dom", side_effect=load), self.assertRaisesRegex(
            RuntimeError, "not transient"
        ):
            self.module.load_roundtrip_dom(
                object(), "https://example.invalid/", "valparaiso", 390, 844, 253
            )
        self.assertEqual(len(calls), 1)


def run_contract() -> dict[str, object]:
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ProductionProbeRetryTests)
    )
    if not result.wasSuccessful():
        raise SystemExit(1)
    return {"tests": result.testsRun, "successful": True}


if __name__ == "__main__":
    run_contract()
