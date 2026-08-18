from __future__ import annotations

import argparse
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

import refresh_balmaceda_valpo_bounded as bounded

# The BAJ server is occasionally slow from GitHub-hosted runners. Keep the
# recovery bounded, but allow one alternate-host retry for the three useful
# landing pages. Discovered detail pages intentionally receive one attempt.
LANDING_TIMEOUTS = (8, 16)
DETAIL_TIMEOUT = 10
RESILIENT_LANDING_URLS = [
    "https://www.balmacedartejoven.cl/sedes/sede-valparaiso/",
    "https://www.balmacedartejoven.cl/sedes/sede-valparaiso/talleres-valparaiso/",
    "https://www.balmacedartejoven.cl/",
]


def candidate_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    candidates = [url]
    if host == "www.balmacedartejoven.cl":
        alt = parsed._replace(netloc="balmacedartejoven.cl")
        candidates.append(urlunparse(alt))
    elif host == "balmacedartejoven.cl":
        alt = parsed._replace(netloc="www.balmacedartejoven.cl")
        candidates.append(urlunparse(alt))
    return candidates


def fetch_once(url: str, timeout: int) -> tuple[bool, int | None, str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0; +https://github.com/carlosggar-arch/agenda-cultural-valparaiso-vina)",
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


def resilient_fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    landing = url in RESILIENT_LANDING_URLS
    timeouts = LANDING_TIMEOUTS if landing else (DETAIL_TIMEOUT,)
    variants = candidate_urls(url)
    failures: list[str] = []
    last_status: int | None = None

    for attempt, timeout in enumerate(timeouts):
        candidate = variants[min(attempt, len(variants) - 1)]
        ok, status, text, error = fetch_once(candidate, timeout)
        last_status = status
        if ok:
            return True, status, text, None
        failures.append(f"attempt={attempt + 1} host={urlparse(candidate).netloc} timeout={timeout}s error={error}")
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
        # Keep the persisted diagnostic truthful about the maximum request timeout.
        bounded.HTTP_TIMEOUT_SECONDS = max(LANDING_TIMEOUTS)
        return bounded.run(no_write=no_write)
    finally:
        bounded.bounded_fetch = old_fetch
        bounded.core.LANDING_URLS = old_landings
        bounded.HTTP_TIMEOUT_SECONDS = old_timeout


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BAJ Valparaíso recovery with bounded retries and alternate-host fallback.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(no_write=args.no_write))


if __name__ == "__main__":
    main()
