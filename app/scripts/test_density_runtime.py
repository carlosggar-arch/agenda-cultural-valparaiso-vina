from __future__ import annotations

import os
import socketserver
import subprocess
import tempfile
import threading
import time

from test_runtime_browser import APP, ROOT, TEST_PAGE, QuietHandler, chrome_binary, make_test_page


def prepare_page(city: str) -> None:
    make_test_page(city)
    source = TEST_PAGE.read_text(encoding="utf-8")
    probe = r'''
  <script type="module" src="./density-polish.js"></script>
  <script>
    setTimeout(() => {
      const header = document.querySelector(".app-header");
      const controls = document.querySelector(".header-bottom");
      const headerRect = header?.getBoundingClientRect();
      const controlsRect = controls?.getBoundingClientRect();
      const chips = [...document.querySelectorAll("[data-category-filter]")];
      const zeroVisible = chips.filter((button) => {
        const count = Number.parseInt(button.querySelector("small")?.textContent || "", 10);
        return count === 0 && getComputedStyle(button).display !== "none" && !button.hidden;
      });

      document.body.dataset.densityControlsPosition = controls ? getComputedStyle(controls).position : "missing";
      document.body.dataset.densityControlsTopGap = headerRect && controlsRect ? String(Math.round(controlsRect.top - headerRect.top)) : "999";
      document.body.dataset.densityControlsRightGap = headerRect && controlsRect ? String(Math.round(headerRect.right - controlsRect.right)) : "999";
      document.body.dataset.densityZeroCategoriesVisible = String(zeroVisible.length);
    }, 7000);
  </script>
'''
    TEST_PAGE.write_text(source.replace("</body>", probe + "\n</body>"), encoding="utf-8")


def run_city(city: str, base_url: str) -> None:
    prepare_page(city)
    with tempfile.TemporaryDirectory(prefix=f"agenda-density-{city}-") as profile:
        cmd = [
            chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--disable-background-networking",
            "--virtual-time-budget=10000", f"--user-data-dir={profile}", "--dump-dom",
            f"{base_url}/app/__runtime_test.html",
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=35)
        if result.returncode != 0:
            raise AssertionError(f"Chrome failed for {city}: {result.stderr[-3000:]}")
        dom = result.stdout
        if 'data-density-controls-position="absolute"' not in dom:
            raise AssertionError(f"Header controls still consume a layout row for {city}")
        if 'data-density-zero-categories-visible="0"' not in dom:
            raise AssertionError(f"A zero-count category remains visible for {city}")

        import re
        top_match = re.search(r'data-density-controls-top-gap="(-?\d+)"', dom)
        right_match = re.search(r'data-density-controls-right-gap="(-?\d+)"', dom)
        if not top_match or not right_match:
            raise AssertionError(f"Could not measure header controls for {city}")
        top_gap = int(top_match.group(1))
        right_gap = int(right_match.group(1))
        if not 0 <= top_gap <= 28:
            raise AssertionError(f"Header controls are not near the top edge for {city}: {top_gap}px")
        if not 0 <= right_gap <= 28:
            raise AssertionError(f"Header controls are not near the right edge for {city}: {right_gap}px")

        print(f"Density runtime {city}: top-right controls and zero empty categories OK")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.2)
        try:
            for city in ("valparaiso", "gijon"):
                run_city(city, f"http://127.0.0.1:{port}")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
