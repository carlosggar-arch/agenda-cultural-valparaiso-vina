from __future__ import annotations

import os
import re
import socketserver
import subprocess
import tempfile
import threading
import time

from test_runtime_browser import APP, ROOT, QuietHandler, chrome_binary, make_test_page

TEST_PAGE = APP / "__runtime_test.html"

DIAGNOSTIC = r'''
<script>
  setTimeout(() => {
    const hitAction = (action) => {
      if (!action) return { hit: null, ok: false };
      action.scrollIntoView({ block: "center", inline: "center" });
      const rect = action.getBoundingClientRect();
      const x = Math.max(1, Math.min(window.innerWidth - 1, rect.left + rect.width / 2));
      const y = Math.max(1, Math.min(window.innerHeight - 1, rect.top + rect.height / 2));
      const hit = document.elementFromPoint(x, y);
      return { hit, ok: Boolean(hit && (hit === action || action.contains(hit))) };
    };

    // Close the detail opened by the baseline runtime probe so we can exercise
    // the card trigger itself using the physical hit target.
    document.querySelector("dialog[data-event-detail]")?.remove();
    const cardTrigger = document.querySelector("[data-open-event]");
    const cardTarget = hitAction(cardTrigger);
    let cardClickObserved = false;
    cardTrigger?.addEventListener("click", () => { cardClickObserved = true; }, { once: true, capture: true });
    cardTarget.hit?.click();

    setTimeout(() => {
      const detail = document.querySelector("dialog[data-event-detail]");
      const actions = detail ? [...detail.querySelectorAll(".event-detail-action")] : [];
      document.body.dataset.eventActionsDiagnosticDone = "true";
      document.body.dataset.cardTriggerHit = String(cardTarget.ok);
      document.body.dataset.cardTriggerClicked = String(cardClickObserved);
      document.body.dataset.eventActionsDetailOpen = String(Boolean(detail?.hasAttribute("open")));
      document.body.dataset.eventActionsCount = String(actions.length);
      document.body.dataset.eventActionsPointerEvents = String(actions.every((action) => getComputedStyle(action).pointerEvents !== "none"));

      let allHit = actions.length > 0;
      for (const action of actions) {
        const result = hitAction(action);
        allHit = allHit && result.ok;
      }
      document.body.dataset.eventActionsHitTargets = String(allHit);

      const link = actions.find((action) => action.tagName === "A");
      let linkClicked = false;
      if (link) {
        link.addEventListener("click", (event) => {
          linkClicked = true;
          event.preventDefault();
        }, { once: true, capture: true });
        const target = hitAction(link);
        target.hit?.click();
      }
      document.body.dataset.eventActionsLinkClicked = String(!link || linkClicked);

      const share = actions.find((action) => action.tagName === "BUTTON" && action.textContent.trim().startsWith("Compartir"));
      let shareClicked = false;
      if (share) {
        share.addEventListener("click", () => { shareClicked = true; }, { once: true, capture: true });
        const target = hitAction(share);
        target.hit?.click();
      }
      document.body.dataset.eventActionsShareClicked = String(!share || shareClicked);

      const panel = detail?.querySelector(".event-detail-panel");
      if (panel) panel.scrollTop = 0;
      const close = detail?.querySelector(".event-detail-close");
      let closeHit = false;
      let closeClickObserved = false;
      let dialogCloseEvent = false;
      close?.addEventListener("click", () => { closeClickObserved = true; }, { once: true, capture: true });
      detail?.addEventListener("close", () => { dialogCloseEvent = true; }, { once: true });
      if (close) {
        const target = hitAction(close);
        closeHit = target.ok;
        target.hit?.click();
      }
      document.body.dataset.eventActionsCloseHit = String(closeHit);
      document.body.dataset.eventActionsCloseClicked = String(closeClickObserved);

      setTimeout(() => {
        document.body.dataset.eventActionsDialogCloseEvent = String(dialogCloseEvent);
        document.body.dataset.eventActionsClosed = String(!document.querySelector("dialog[data-event-detail]"));
      }, 500);
    }, 250);
  }, 7600);
</script>
'''


def make_action_test_page(city: str) -> None:
    make_test_page(city)
    source = TEST_PAGE.read_text(encoding="utf-8")
    TEST_PAGE.write_text(source.replace("</body>", DIAGNOSTIC + "\n</body>", 1), encoding="utf-8")


def dump_dom(city: str, url: str) -> str:
    errors: list[str] = []
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"agenda-actions-{city}-{attempt}-", ignore_cleanup_errors=True) as profile:
            cmd = [
                chrome_binary(), "--headless=new", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--disable-background-networking",
                "--disable-extensions", "--disable-sync", "--no-first-run", "--no-default-browser-check",
                "--host-resolver-rules=MAP * 127.0.0.1, EXCLUDE 127.0.0.1",
                "--window-size=390,844", "--virtual-time-budget=11200",
                f"--user-data-dir={profile}", "--dump-dom", url,
            ]
            try:
                result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=45)
            except subprocess.TimeoutExpired:
                errors.append(f"attempt {attempt}: Chrome timed out")
                time.sleep(1)
                continue
            if result.returncode == 0 and result.stdout:
                return result.stdout
            errors.append(f"attempt {attempt}: exit={result.returncode}; stderr={result.stderr[-1200:]}")
            time.sleep(1)
    raise AssertionError(f"Event-action browser diagnostic failed for {city}: {' | '.join(errors)}")


def run_city(city: str, base_url: str) -> None:
    make_action_test_page(city)
    dom = dump_dom(city, f"{base_url}/app/__runtime_test.html")
    markers = {
        'data-event-actions-diagnostic-done="true"': "diagnostic did not finish",
        'data-card-trigger-hit="true"': "card action is covered by another hit target",
        'data-card-trigger-clicked="true"': "card action did not receive the physical click",
        'data-event-actions-detail-open="true"': "event detail did not open from the physical card click",
        'data-event-actions-pointer-events="true"': "an action has pointer-events disabled",
        'data-event-actions-hit-targets="true"': "an overlay intercepts at least one event action",
        'data-event-actions-link-clicked="true"': "external action did not receive the physical hit",
        'data-event-actions-share-clicked="true"': "share action did not receive the physical hit",
        'data-event-actions-close-hit="true"': "close control is not the physical hit target",
        'data-event-actions-close-clicked="true"': "close control did not receive the click event",
        'data-event-actions-dialog-close-event="true"': "dialog close event did not fire",
        'data-event-actions-closed="true"': "close control did not remove the detail",
    }
    missing = [message for marker, message in markers.items() if marker not in dom]
    count = re.search(r'data-event-actions-count="(\d+)"', dom)
    if not count or int(count.group(1)) < 2:
        missing.append("too few event actions rendered")
    if missing:
        observed = ", ".join(re.findall(r'data-(?:card-trigger|event-actions)-[a-z-]+="[^"]*"', dom))
        raise AssertionError(f"{city}: {'; '.join(missing)}; observed: {observed}")
    print(f"Event action interaction {city}: card trigger plus {count.group(1)} detail controls receive physical clicks and close works")


def main() -> None:
    os.chdir(ROOT)
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start(); time.sleep(0.2)
        try:
            for city in ("valparaiso", "gijon"):
                run_city(city, f"http://127.0.0.1:{port}")
        finally:
            server.shutdown(); thread.join(timeout=2); TEST_PAGE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
