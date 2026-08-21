from __future__ import annotations

import tempfile
import time

from production_pwa_smoke import (
    ORIGINS,
    assert_loaded_dom,
    chrome_binary,
    expected_shell,
    profile_dom,
    release_number,
)

MOBILE_CITY = "valparaiso"
MOBILE_LABEL = "Valparaíso / Viña del Mar"
MOBILE_WIDTH = 390
MOBILE_HEIGHT = 844
MAX_WARM_RATIO = 1.75
MAX_WARM_EXTRA_SECONDS = 4.0


def timed_profile_dom(chrome: str, profile: str, base: str, attempts: int = 2) -> tuple[str, float]:
    last_error = ""
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            dom = profile_dom(chrome, profile, base, MOBILE_CITY, MOBILE_WIDTH, MOBILE_HEIGHT)
            return dom, time.monotonic() - started
        except Exception as exc:
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(2)
    raise RuntimeError(f"Chrome warm probe failed after retry: {last_error}")


def main() -> None:
    expected_release = release_number()
    expected = expected_shell()
    chrome = chrome_binary()

    for origin, base in ORIGINS.items():
        with tempfile.TemporaryDirectory(prefix=f"vivamos-warm-{origin}-") as profile:
            cold_dom, cold_seconds = timed_profile_dom(chrome, profile, base)
            assert_loaded_dom(
                cold_dom,
                origin,
                MOBILE_CITY,
                MOBILE_LABEL,
                MOBILE_WIDTH,
                MOBILE_HEIGHT,
                expected_release,
                expected,
            )

            warm_dom, warm_seconds = timed_profile_dom(chrome, profile, base)
            assert_loaded_dom(
                warm_dom,
                origin,
                MOBILE_CITY,
                MOBILE_LABEL,
                MOBILE_WIDTH,
                MOBILE_HEIGHT,
                expected_release,
                expected,
            )

            # Broad regression guard, not a benchmark: network and runner jitter
            # can move absolute timings, but the same-profile reopen must not
            # become catastrophically slower than the preceding cold load.
            warm_limit = max(
                cold_seconds * MAX_WARM_RATIO,
                cold_seconds + MAX_WARM_EXTRA_SECONDS,
            )
            if warm_seconds > warm_limit:
                raise SystemExit(
                    "Warm mobile reopen regressed: "
                    f"origin={origin} cold={cold_seconds:.2f}s warm={warm_seconds:.2f}s "
                    f"limit={warm_limit:.2f}s"
                )

            ratio = cold_seconds / warm_seconds if warm_seconds > 0 else float("inf")
            print(
                "PRODUCTION_WARM_REOPEN_OK "
                f"origin={origin} release=v{expected_release} viewport={MOBILE_WIDTH}x{MOBILE_HEIGHT} "
                f"cold={cold_seconds:.2f}s warm={warm_seconds:.2f}s speedup={ratio:.2f}x"
            )


if __name__ == "__main__":
    main()
