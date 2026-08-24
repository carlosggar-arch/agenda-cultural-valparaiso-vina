from __future__ import annotations

import hashlib
import time
from pathlib import Path

from production_pwa_smoke import ORIGINS, ROOT, fetch_bytes

ADMIN_PATH = Path("admin-staging/index.html")
REMOTE_PATH = "admin-staging/index.html"
REQUIRED_MARKERS = (
    "PRODUCCIÓN CANÓNICA",
    "PREVIEW DE PR · NO PRODUCCIÓN",
    "Un preview nunca certifica ni invalida la producción",
    "vivamos-production-certification-history",
    "state/production-certifications/data/index.json",
)


def root_origin(app_base: str) -> str:
    if not app_base.endswith("app/"):
        raise SystemExit(f"Unexpected production app base: {app_base}")
    return app_base[: -len("app/")]


def verify_origin(name: str, app_base: str, *, attempts: int = 36, interval: int = 10) -> None:
    local = ROOT / ADMIN_PATH
    expected_bytes = local.read_bytes()
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()
    expected_text = expected_bytes.decode("utf-8")
    for marker in REQUIRED_MARKERS:
        if marker not in expected_text:
            raise SystemExit(f"Local admin staging is missing required environment marker: {marker}")

    base = root_origin(app_base)
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            actual_bytes = fetch_bytes(base, REMOTE_PATH)
            actual_hash = hashlib.sha256(actual_bytes).hexdigest()
            if actual_hash != expected_hash:
                last = f"byte mismatch actual={actual_hash} expected={expected_hash}"
            else:
                actual_text = actual_bytes.decode("utf-8", errors="replace")
                missing = [marker for marker in REQUIRED_MARKERS if marker not in actual_text]
                if not missing:
                    print(
                        "PRODUCTION_ADMIN_STAGING_PARITY_OK "
                        f"origin={name} sha256={actual_hash} environments=production,preview history=permanent"
                    )
                    return
                last = f"missing markers={missing}"
        except Exception as exc:
            last = str(exc)
        if attempt == attempts:
            raise SystemExit(f"Admin staging did not reach production parity on {name}: {last}")
        time.sleep(interval)


def main() -> int:
    for name, app_base in ORIGINS.items():
        verify_origin(name, app_base)
    print("PRODUCTION_ADMIN_STAGING_VERIFIED origins=github-pages,cloudflare preview_is_not_production=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
