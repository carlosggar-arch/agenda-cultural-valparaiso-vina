from __future__ import annotations

import argparse
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

import refresh_balmaceda_valpo_bounded as bounded

# BAJ is intermittently unreachable from GitHub-hosted Azure runners through
# Python's default transport. Keep a strict request budget and fall back to
# curl with IPv4 + HTTP/1.1 before declaring the official source unreachable.
URLLIB_LANDING_TIMEOUT = 8
CURL_LANDING_TIMEOUT = 12
DETAIL_URLLIB_TIMEOUT = 8
DETAIL_CURL_TIMEOUT = 10
RESILIENT_LANDING_URLS = [
    "https://www.balmacedartejoven.cl/sedes/sede-valparaiso/",
    "https://www.balmacedartejoven.cl/sedes/sede-valparaiso/talleres-valparaiso/",
    "https://www.balmacedartejoven.cl/",
]
USER_AGENT = "Mozilla/5.0 (compatible; AgendaCultural/1.0; +https://github.com/carlosggar-arch/agenda-cultural-valparaiso-vina)"


def candidate_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    candidates = [url]
    if host == "www.balmacedartejoven.cl":
        candidates.append(urlunparse(parsed._replace(netloc="balmacedartejoven.cl")))
    elif host == "balmacedartejoven.cl":
        candidates.append(urlunparse(parsed._replace(netloc="www.balmacedartejoven.cl")))
    return candidates


def fetch_once(url: str, timeout: int) -> tuple[bool, int | None, str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "close",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed official HTTPS host
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            return True, getattr(response, "status", 200), text, None
    except HTTPError as exc:
        return False, exc.code, "", f"HTTP {exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return False, None, "", f"{type(exc).__name__}: {exc}"


def fetch_once_curl(url: str, timeout: int) -> tuple[bool, int | None, str, str | None]:
    marker = "\n__AGENDA_HTTP_STATUS__="
    command = [
        "curl",
        "-4",
        "--http1.1",
        "--location",
        "--silent",
        "--show-error",
        "--connect-timeout",
        str(min(6, timeout)),
        "--max-time",
        str(timeout),
        "--user-agent",
        USER_AGENT,
        "--header",
        "Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "--header",
        "Accept-Language: es-CL,es;q=0.9,en;q=0.6",
        "--write-out",
        marker + "%{http_code}",
        url,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 3, check=False)  # nosec B603 - fixed curl command and official URLs
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, None, "", f"curl_transport:{type(exc).__name__}: {exc}"

    output = result.stdout or ""
    match = re.search(r"\n__AGENDA_HTTP_STATUS__=(\d{3})\s*$", output)
    status = int(match.group(1)) if match else None
    body = output[: match.start()] if match else output
    if result.returncode == 0 and status is not None and 200 <= status < 400:
        return True, status, body, None
    error = (result.stderr or "").strip() or f"curl_exit_{result.returncode}"
    return False, status, "", error


def resilient_fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    landing = url in RESILIENT_LANDING_URLS
    variants = candidate_urls(url)
    failures: list[str] = []
    last_status: int | None = None

    strategies: list[tuple[str, str, int]] = []
    if landing:
        strategies.append(("urllib", variants[0], URLLIB_LANDING_TIMEOUT))
        strategies.append(("curl4", variants[0], CURL_LANDING_TIMEOUT))
        if len(variants) > 1:
            strategies.append(("curl4-alt-host", variants[1], CURL_LANDING_TIMEOUT))
    else:
        strategies.append(("urllib", variants[0], DETAIL_URLLIB_TIMEOUT))
        strategies.append(("curl4", variants[0], DETAIL_CURL_TIMEOUT))

    for attempt, (transport, candidate, timeout) in enumerate(strategies, start=1):
        fetcher = fetch_once if transport == "urllib" else fetch_once_curl
        ok, status, text, error = fetcher(candidate, timeout)
        last_status = status
        if ok:
            return True, status, text, None
        failures.append(
            f"attempt={attempt} transport={transport} host={urlparse(candidate).netloc} timeout={timeout}s error={error}"
        )
        # Retrying 4xx responses is not useful. 5xx/network failures may recover.
        if status is not None and 400 <= status < 500:
            break

    return False, last_status, "", "; ".join(failures) or "fetch_failed"


def run(no_write: bool = False) -> int:
    old_fetch = bounded.bounded_fetch
    old_landings = list(bounded.core.LANDING_URLS)
    old_timeout = bounded.HTTP_TIMEOUT_SECONDS
    try:
        bounded.bounded_fetch = resilient_fetch
        bounded.core.LANDING_URLS = list(RESILIENT_LANDING_URLS)
        # Persist the largest single-request timeout used by the transport.
        bounded.HTTP_TIMEOUT_SECONDS = CURL_LANDING_TIMEOUT
        return bounded.run(no_write=no_write)
    finally:
        bounded.bounded_fetch = old_fetch
        bounded.core.LANDING_URLS = old_landings
        bounded.HTTP_TIMEOUT_SECONDS = old_timeout


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run BAJ Valparaíso recovery with bounded retries, forced IPv4 and alternate-host fallback."
    )
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(no_write=args.no_write))


if __name__ == "__main__":
    main()
