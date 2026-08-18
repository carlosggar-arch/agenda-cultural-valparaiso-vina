from __future__ import annotations

import argparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import refresh_balmaceda_valpo as core

MAX_LINKS_PER_LANDING = 2
HTTP_TIMEOUT_SECONDS = 6


def bounded_fetch(url: str) -> tuple[bool, int | None, str, str | None]:
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AgendaCultural/1.0)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9",
    })
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # nosec B310 - official configured HTTPS URLs
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


def install_bounds() -> None:
    original_discover = core.discover_links

    def bounded_discover(markup: str) -> list[str]:
        return original_discover(markup)[:MAX_LINKS_PER_LANDING]

    core.fetch = bounded_fetch
    core.discover_links = bounded_discover


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Balmaceda official refresh with strict network bounds.")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    install_bounds()
    raise SystemExit(core.run(args.no_write))


if __name__ == "__main__":
    main()
