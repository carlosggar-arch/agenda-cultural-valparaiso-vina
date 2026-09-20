from __future__ import annotations

import unittest

from production_probe_retry import retry_call


class ProductionProbeRetryTests(unittest.TestCase):
    def test_transient_declared_failure_is_retried_once(self) -> None:
        calls = []
        retries = []

        def operation() -> str:
            calls.append("call")
            if len(calls) == 1:
                raise TimeoutError("transient")
            return "ready"

        result = retry_call(
            operation,
            attempts=2,
            retry_on=(TimeoutError,),
            on_retry=lambda attempt, total: retries.append((attempt, total)),
        )

        self.assertEqual(result, "ready")
        self.assertEqual(len(calls), 2)
        self.assertEqual(retries, [(2, 2)])

    def test_persistent_declared_failure_remains_terminal(self) -> None:
        calls = []

        def operation() -> None:
            calls.append("call")
            raise TimeoutError("persistent")

        with self.assertRaisesRegex(TimeoutError, "persistent"):
            retry_call(
                operation,
                attempts=2,
                retry_on=(TimeoutError,),
                on_retry=lambda _attempt, _total: None,
            )
        self.assertEqual(len(calls), 2)

    def test_undeclared_failure_is_not_retried(self) -> None:
        calls = []

        def operation() -> None:
            calls.append("call")
            raise RuntimeError("not transient")

        with self.assertRaisesRegex(RuntimeError, "not transient"):
            retry_call(
                operation,
                attempts=2,
                retry_on=(TimeoutError,),
                on_retry=lambda _attempt, _total: None,
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
