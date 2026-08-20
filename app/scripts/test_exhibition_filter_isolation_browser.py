from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEST_PAGE = APP / "__exhibition_filter_isolation.html"


def chrome_binary() -> str:
    for candidate in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("No Chromium/Chrome binary available on the runner")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def make_test_page() -> None:
    source = (APP / "index.html").read_text(encoding="utf-8")
    probe = r'''
<script data-exhibition-filter-isolation-probe>
(() => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const visible = (node) => {
    if (!node || node.hidden || node.closest('[hidden]')) return false;
    const style = getComputedStyle(node);
    return style.display !== 'none' && style.visibility !== 'hidden' && node.getClientRects().length > 0;
  };
  const visibleGroups = () => [...document.querySelectorAll('[data-unified-exhibition-group="true"]')].filter(visible);
  const chip = (id) => document.querySelector(`[data-combined-category="${CSS.escape(id)}"]`);
  const waitFor = async (predicate, timeout = 7000) => {
    const started = performance.now();
    while (performance.now() - started < timeout) {
      const value = predicate();
      if (value) return value;
      await sleep(80);
    }
    return null;
  };

  async function run() {
    try {
      await waitFor(() => visibleGroups().length > 0);
      const nonExhibition = await waitFor(() => [...document.querySelectorAll('[data-combined-category]')]
        .find((button) => button.dataset.combinedCategory !== 'exposiciones' && Number(button.querySelector('small')?.textContent || 0) > 0));
      if (!nonExhibition) throw new Error('No non-exhibition category with results found');

      const nonId = nonExhibition.dataset.combinedCategory;
      nonExhibition.click();
      await sleep(700);
      const nonGroups = visibleGroups().length;
      const nonActive = chip(nonId)?.getAttribute('aria-pressed') === 'true';

      chip(nonId)?.click();
      await sleep(300);
      const exhibitions = await waitFor(() => chip('exposiciones'));
      if (!exhibitions) throw new Error('Exposiciones category chip not found');
      exhibitions.click();
      await sleep(700);
      const expoGroups = visibleGroups().length;
      const expoActive = chip('exposiciones')?.getAttribute('aria-pressed') === 'true';

      document.body.dataset.exhibitionFilterIsolationReady = 'true';
      document.body.dataset.exhibitionFilterNonCategory = nonId || '';
      document.body.dataset.exhibitionFilterNonActive = nonActive ? 'true' : 'false';
      document.body.dataset.exhibitionFilterGroupsUnderNon = String(nonGroups);
      document.body.dataset.exhibitionFilterExpoActive = expoActive ? 'true' : 'false';
      document.body.dataset.exhibitionFilterGroupsUnderExpo = String(expoGroups);
    } catch (error) {
      document.body.dataset.exhibitionFilterIsolationReady = 'error';
      document.body.dataset.exhibitionFilterIsolationError = String(error?.message || error);
    }
  }

  window.addEventListener('vivamos:exhibition-groups-rendered', () => setTimeout(run, 120), { once: true });
  setTimeout(() => {
    if (!document.body.dataset.exhibitionFilterIsolationReady) run();
  }, 1800);
})();
</script>
'''
    source = source.replace("</body>", probe + "\n</body>", 1)
    TEST_PAGE.write_text(source, encoding="utf-8")


def dump_dom(url: str) -> str:
    with tempfile.TemporaryDirectory(prefix="vivamos-exhibition-filter-", ignore_cleanup_errors=True) as profile:
        cmd = [
            chrome_binary(),
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-extensions",
            "--disable-sync",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1360,1000",
            "--virtual-time-budget=10500",
            f"--user-data-dir={profile}",
            "--dump-dom",
            url,
        ]
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=40)
        if result.returncode != 0 or not result.stdout:
            raise AssertionError(f"Chrome exhibition-filter probe failed: {result.stderr[-1600:]}")
        return result.stdout


def attr(dom: str, name: str) -> str:
    match = re.search(rf'\b{re.escape(name)}="([^"]*)"', dom)
    return match.group(1) if match else "(absent)"


def main() -> None:
    os.chdir(ROOT)
    make_test_page()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    try:
        with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            time.sleep(0.2)
            try:
                dom = dump_dom(f"http://127.0.0.1:{port}/app/{TEST_PAGE.name}?city=gijon&when=todos")
            finally:
                server.shutdown()
                thread.join(timeout=2)
    finally:
        TEST_PAGE.unlink(missing_ok=True)

    diagnostics = {
        "ready": attr(dom, "data-exhibition-filter-isolation-ready"),
        "non_category": attr(dom, "data-exhibition-filter-non-category"),
        "non_active": attr(dom, "data-exhibition-filter-non-active"),
        "groups_under_non": attr(dom, "data-exhibition-filter-groups-under-non"),
        "expo_active": attr(dom, "data-exhibition-filter-expo-active"),
        "groups_under_expo": attr(dom, "data-exhibition-filter-groups-under-expo"),
        "error": attr(dom, "data-exhibition-filter-isolation-error"),
    }
    print("EXHIBITION_FILTER_ISOLATION_DIAGNOSTICS " + json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    assert diagnostics["ready"] == "true", f"filter isolation probe did not finish: {diagnostics}"
    assert diagnostics["non_active"] == "true", f"non-exhibition category did not become active: {diagnostics}"
    assert diagnostics["groups_under_non"] == "0", (
        "grouped exhibitions must be hidden when a non-exhibition category is selected; "
        f"diagnostics={diagnostics}"
    )
    assert diagnostics["expo_active"] == "true", f"Exposiciones category did not become active: {diagnostics}"
    assert int(diagnostics["groups_under_expo"]) > 0, f"grouped exhibitions must reappear under Exposiciones: {diagnostics}"
    print("Exhibition category isolation browser contract: OK")


if __name__ == "__main__":
    main()
