from __future__ import annotations

import refresh_balmaceda_valpo_resilient as transport


def test_candidate_urls_toggle_www_host() -> None:
    urls = transport.candidate_urls("https://www.balmacedartejoven.cl/sedes/sede-valparaiso/")
    assert urls[0].startswith("https://www.balmacedartejoven.cl/")
    assert urls[1].startswith("https://balmacedartejoven.cl/")


def test_landing_retries_on_alternate_host() -> None:
    original = transport.fetch_once
    calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, timeout: int):
        calls.append((url, timeout))
        if len(calls) == 1:
            return False, None, "", "TimeoutError: simulated"
        return True, 200, "<html>ok</html>", None

    transport.fetch_once = fake_fetch
    try:
        ok, status, text, error = transport.resilient_fetch(transport.RESILIENT_LANDING_URLS[0])
    finally:
        transport.fetch_once = original

    assert ok is True
    assert status == 200
    assert text == "<html>ok</html>"
    assert error is None
    assert len(calls) == 2
    assert calls[0][1] == 8
    assert calls[1][1] == 16
    assert "www.balmacedartejoven.cl" in calls[0][0]
    assert "https://balmacedartejoven.cl/" in calls[1][0]


def test_detail_page_does_not_multiply_retries() -> None:
    original = transport.fetch_once
    calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, timeout: int):
        calls.append((url, timeout))
        return False, None, "", "TimeoutError: simulated"

    transport.fetch_once = fake_fetch
    try:
        ok, status, text, error = transport.resilient_fetch(
            "https://www.balmacedartejoven.cl/noticias/valparaiso/actividad-prueba/"
        )
    finally:
        transport.fetch_once = original

    assert ok is False
    assert status is None
    assert text == ""
    assert "attempt=1" in str(error)
    assert len(calls) == 1
    assert calls[0][1] == transport.DETAIL_TIMEOUT


def test_client_errors_are_not_retried() -> None:
    original = transport.fetch_once
    calls: list[tuple[str, int]] = []

    def fake_fetch(url: str, timeout: int):
        calls.append((url, timeout))
        return False, 404, "", "HTTP 404"

    transport.fetch_once = fake_fetch
    try:
        ok, status, _, _ = transport.resilient_fetch(transport.RESILIENT_LANDING_URLS[0])
    finally:
        transport.fetch_once = original

    assert ok is False
    assert status == 404
    assert len(calls) == 1


def main() -> None:
    test_candidate_urls_toggle_www_host()
    test_landing_retries_on_alternate_host()
    test_detail_page_does_not_multiply_retries()
    test_client_errors_are_not_retried()
    print("BALMACEDA_TRANSPORT_TESTS_OK")


if __name__ == "__main__":
    main()
