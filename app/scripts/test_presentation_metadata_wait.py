"""Regression for a slow but complete presentation pass on a cold origin."""

from __future__ import annotations

from selenium.common.exceptions import TimeoutException

import test_web_pwa_visibility_parity as parity


class FakeDriver:
    def __init__(self, states: list[dict[str, object]]) -> None:
        self.states = iter(states)
        self.last = states[-1]

    def execute_script(self, _script: str) -> dict[str, object]:
        self.last = next(self.states, self.last)
        return self.last


def main() -> None:
    original_wait = parity.WebDriverWait
    seen: list[float] = []

    class DelayedWait:
        def __init__(self, driver: FakeDriver, timeout: float, **_kwargs: object) -> None:
            self.driver = driver
            seen.append(timeout)

        def until(self, predicate):
            assert predicate(self.driver) is False
            assert predicate(self.driver) is True

    incomplete = {"ready": False, "visible_cards": 24, "missing_metadata": 1,
                  "missing_ids": ["agenda_test"]}
    complete = {"ready": True, "visible_cards": 24, "missing_metadata": 0,
                "missing_ids": []}
    try:
        parity.WebDriverWait = DelayedWait
        parity.wait_presentation_metadata(
            FakeDriver([incomplete, complete]), origin="cloudflare", city="gijon",
            phase="online", state="hoy",
        )
        assert seen == [parity.READY_TIMEOUT]

        class NeverReadyWait(DelayedWait):
            def until(self, predicate):
                assert predicate(self.driver) is False
                raise TimeoutException()

        parity.WebDriverWait = NeverReadyWait
        try:
            parity.wait_presentation_metadata(
                FakeDriver([incomplete]), origin="cloudflare", city="gijon",
                phase="pwa", state="7-dias",
            )
        except AssertionError as exc:
            message = str(exc)
            assert "origin=cloudflare city=gijon phase=pwa state=7-dias" in message
            assert "missing_metadata=1" in message
            assert "agenda_test" in message
        else:
            raise AssertionError("Missing metadata must remain a failing smoke")
    finally:
        parity.WebDriverWait = original_wait
    print("PRESENTATION_METADATA_WAIT_OK")


if __name__ == "__main__":
    main()
