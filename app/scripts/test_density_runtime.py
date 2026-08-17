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
      const discovery = document.querySelector("[data-discovery]");
      if (discovery) discovery.hidden = false;

      const header = document.querySelector(".app-header");
      const controls = document.querySelector(".header-bottom");
      const headerRect = header?.getBoundingClientRect();
      const controlsRect = controls?.getBoundingClientRect();
      const chips = [...document.querySelectorAll("[data-category-filter]")];
      const zeroVisible = chips.filter((button) => {
        const count = Number.parseInt(button.querySelector("small")?.textContent || "", 10);
        return count === 0 && getComputedStyle(button).display !== "none" && !button.hidden;
      });
      const workbench = document.querySelector(".filter-workbench");
      const dividerStyle = workbench ? getComputedStyle(workbench, "::before") : null;
      const whenRow = document.querySelector("[data-combined-when]");
      const whenRowStyle = whenRow ? getComputedStyle(whenRow) : null;
      const whenTitleStyle = whenRow ? getComputedStyle(whenRow, "::before") : null;

      document.body.dataset.densityControlsPosition = controls ? getComputedStyle(controls).position : "missing";
      document.body.dataset.densityControlsTopGap = headerRect && controlsRect ? String(Math.round(controlsRect.top - headerRect.top)) : "999";
      document.body.dataset.densityControlsRightGap = headerRect && controlsRect ? String(Math.round(headerRect.right - controlsRect.right)) : "999";
      document.body.dataset.densityZeroCategoriesVisible = String(zeroVisible.length);
      document.body.dataset.densityMosaicVisible = String(Boolean(
        dividerStyle
        && dividerStyle.content !== "none"
        && Number.parseFloat(dividerStyle.height) >= 8
        && dividerStyle.backgroundImage.includes("mosaic-top.png")
      ));
      document.body.dataset.densityWhenTitleVisible = String(Boolean(
        whenTitleStyle
        && whenTitleStyle.content.includes("Cuándo")
        && whenTitleStyle.display !== "none"
        && whenTitleStyle.visibility !== "hidden"
        && Number.parseFloat(whenTitleStyle.top || "-1") >= 0
      ));
      document.body.dataset.densityWhenLineHeight = String(
        Math.round(Number.parseFloat(whenTitleStyle?.lineHeight || "0"))
      );
      document.body.dataset.densityWhenPaddingTop = String(
        Math.round(Number.parseFloat(whenRowStyle?.paddingTop || "0"))
      );
    }, 7000);
  </script>
'''
    TEST_PAGE.write_text(source.replace("</body>", probe + "\n</body>"), encoding="utf-8")


def dump_dom(city: str, url: str) -> str:
    errors: list[str] = []
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"agenda-density-{city}-{attempt}-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
                "--virtual-time-budget=10000", f"--user-data-dir={profile}", "--dump-dom", url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=40)
            except subprocess.TimeoutExpired:
                errors.append(f"attempt {attempt}: Chrome timed out")
                time.sleep(1)
                continue
            if result.returncode == 0 and result.stdout:
                return result.stdout
            errors.append(f"attempt {attempt}: exit={result.returncode}; stderr={result.stderr[-1200:]}")
            time.sleep(1)
    raise AssertionError(f"Density browser probe failed for {city}: {' | '.join(errors)}")


def run_city(city: str, base_url: str) -> None:
    prepare_page(city)
    dom = dump_dom(city, f"{base_url}/app/__runtime_test.html")
    if 'data-density-controls-position="absolute"' not in dom:
        raise AssertionError(f"Header controls still consume a layout row for {city}")
    if 'data-density-zero-categories-visible="0"' not in dom:
        raise AssertionError(f"A zero-count category remains visible for {city}")
    if 'data-density-mosaic-visible="true"' not in dom:
        raise AssertionError(f"The compact mosaic divider is not visible for {city}")
    if 'data-density-when-title-visible="true"' not in dom:
        raise AssertionError(f"The stable visual When title is not rendered for {city}")

    import re
    top_match = re.search(r'data-density-controls-top-gap="(-?\d+)"', dom)
    right_match = re.search(r'data-density-controls-right-gap="(-?\d+)"', dom)
    line_height_match = re.search(r'data-density-when-line-height="(\d+)"', dom)
    padding_match = re.search(r'data-density-when-padding-top="(\d+)"', dom)
    if not top_match or not right_match:
        raise AssertionError(f"Could not measure header controls for {city}")
    if not line_height_match or not padding_match:
        raise AssertionError(f"Could not measure the When filter spacing for {city}")
    top_gap = int(top_match.group(1))
    right_gap = int(right_match.group(1))
    line_height = int(line_height_match.group(1))
    padding_top = int(padding_match.group(1))
    if not 0 <= top_gap <= 28:
        raise AssertionError(f"Header controls are not near the top edge for {city}: {top_gap}px")
    if not 0 <= right_gap <= 28:
        raise AssertionError(f"Header controls are not near the right edge for {city}: {right_gap}px")
    if line_height < 10:
        raise AssertionError(f"When title line-height remains cramped for {city}: {line_height}px")
    if padding_top < 20:
        raise AssertionError(f"When row has insufficient top breathing room for {city}: {padding_top}px")

    print(f"Density runtime {city}: compact header, mosaic divider and readable When filter OK")


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
