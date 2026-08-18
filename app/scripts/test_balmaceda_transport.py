from __future__ import annotations

import refresh_balmaceda_valpo_resilient as transport


def test_candidate_urls_toggle_www_host() -> None:
    urls = transport.candidate_urls("https://www.balmacedartejoven.cl/sedes/sede-valparaiso/")
    assert urls[0].startswith("https://www.balmacedartejoven.cl/")
    assert urls[1].startswith("https://balmacedartejoven.cl/")


def test_landing_falls_back_from_urllib_to_curl4() -> None:
    original_urllib = transport.fetch_once
    original_curl = transport.fetch_once_curl
    urllib_calls: list[tuple[str, int]] = []
    curl_calls: list[tuple[str, int]] = []

    def fake_urllib(url: str, timeout: int):
        urllib_calls.append((url, timeout))
        return False, None, "", "TimeoutError: simulated"

    def fake_curl(url: str, timeout: int):
        curl_calls.append((url, timeout))
        return True, 200, "<html>ok</html>", None

    transport.fetch_once = fake_urllib
    transport.fetch_once_curl = fake_curl
    try:
        ok, status, text, error = transport.resilient_fetch(transport.RESILIENT_LANDING_URLS[0])
    finally:
        transport.fetch_once = original_urllib
        transport.fetch_once_curl = original_curl

    assert ok is True
    assert status == 200
    assert text == "<html>ok</html>"
    assert error is None
    assert urllib_calls == [(transport.RESILIENT_LANDING_URLS[0], transport.URLLIB_LANDING_TIMEOUT)]
    assert curl_calls == [(transport.RESILIENT_LANDING_URLS[0], transport.CURL_LANDING_TIMEOUT)]


def test_landing_uses_alternate_host_after_curl4_failure() -> None:
    original_urllib = transport.fetch_once
    original_curl = transport.fetch_once_curl
    curl_calls: list[tuple[str, int]] = []

    def fake_urllib(url: str, timeout: int):
        return False, None, "", "TimeoutError: simulated"

    def fake_curl(url: str, timeout: int):
        curl_calls.append((url, timeout))
        if len(curl_calls) == 1:
            return False, None, "", "curl timeout"
        return True, 200, "<html>alt-ok</html>", None

    transport.fetch_once = fake_urllib
    transport.fetch_once_curl = fake_curl
    try:
        ok, status, text, error = transport.resilient_fetch(transport.RESILIENT_LANDING_URLS[0])
    finally:
        transport.fetch_once = original_urllib
        transport.fetch_once_curl = original_curl

    assert ok is True
    assert status == 200
    assert text == "<html>alt-ok</html>"
    assert error is None
    assert len(curl_calls) == 2
    assert "www.balmacedartejoven.cl" in curl_calls[0][0]
    assert "https://balmacedartejoven.cl/" in curl_calls[1][0]


def test_detail_page_has_two_bounded_transports_only() -> None:
    original_urllib = transport.fetch_once
    original_curl = transport.fetch_once_curl
    calls: list[tuple[str, str, int]] = []

    def fake_urllib(url: str, timeout: int):
        calls.append(("urllib", url, timeout))
        return False, None, "", "TimeoutError: simulated"

    def fake_curl(url: str, timeout: int):
        calls.append(("curl4", url, timeout))
        return False, None, "", "curl timeout"

    transport.fetch_once = fake_urllib
    transport.fetch_once_curl = fake_curl
    try:
        ok, status, text, error = transport.resilient_fetch(
            "https://www.balmacedartejoven.cl/noticias/valparaiso/actividad-prueba/"
        )
    finally:
        transport.fetch_once = original_urllib
        transport.fetch_once_curl = original_curl

    assert ok is False
    assert status is None
    assert text == ""
    assert "attempt=1" in str(error) and "attempt=2" in str(error)
    assert [row[0] for row in calls] == ["urllib", "curl4"]
    assert calls[0][2] == transport.DETAIL_URLLIB_TIMEOUT
    assert calls[1][2] == transport.DETAIL_CURL_TIMEOUT


def test_client_errors_are_not_retried() -> None:
    original_urllib = transport.fetch_once
    original_curl = transport.fetch_once_curl
    curl_calls: list[tuple[str, int]] = []

    def fake_urllib(url: str, timeout: int):
        return False, 404, "", "HTTP 404"

    def fake_curl(url: str, timeout: int):
        curl_calls.append((url, timeout))
        return False, 404, "", "HTTP 404"

    transport.fetch_once = fake_urllib
    transport.fetch_once_curl = fake_curl
    try:
        ok, status, _, _ = transport.resilient_fetch(transport.RESILIENT_LANDING_URLS[0])
    finally:
        transport.fetch_once = original_urllib
        transport.fetch_once_curl = original_curl

    assert ok is False
    assert status == 404
    assert curl_calls == []


def main() -> None:
    test_candidate_urls_toggle_www_host()
    test_landing_falls_back_from_urllib_to_curl4()
    test_landing_uses_alternate_host_after_curl4_failure()
    test_detail_page_has_two_bounded_transports_only()
    test_client_errors_are_not_retried()
    print("BALMACEDA_TRANSPORT_TESTS_OK")


if __name__ == "__main__":
    main()
