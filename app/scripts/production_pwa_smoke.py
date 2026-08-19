from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
BASE = "https://carlosggar-arch.github.io/agenda-cultural-valparaiso-vina/app/"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def release_number() -> int:
    match = re.search(r"const RELEASE = (\d+);", read("app/release-version.js"))
    if not match:
        raise SystemExit("release-version.js has no numeric RELEASE")
    return int(match.group(1))


def expected_shell() -> dict[str, str]:
    index = read("app/index.html")
    pwa = read("app/pwa.js")
    header = read("app/header-redesign.js")

    header_style = re.search(r'const HEADER_STYLESHEET = "([^"]+)"', header)
    mobile_style = re.search(
        r'<link rel="stylesheet" href="([^"]*mobile-experience\.css[^"]*)" data-mobile-experience-styles>',
        index,
    )
    header_module = re.search(r'import "(\./header-redesign\.js[^\"]*)";', pwa)
    mobile_module = re.search(r'import "(\./mobile-experience\.js[^\"]*)";', pwa)
    if not all((header_style, mobile_style, header_module, mobile_module)):
        raise SystemExit("Unable to derive canonical PWA shell references from local sources")
    return {
        "header_style": header_style.group(1),
        "mobile_style": mobile_style.group(1),
        "header_module": header_module.group(1),
        "mobile_module": mobile_module.group(1),
    }


def local_contract() -> None:
    expected = expected_shell()
    index = read("app/index.html")
    pwa = read("app/pwa.js")
    worker = read("app/service-worker.js")

    required_index = (
        '<script src="./release-version.js"></script>',
        expected["header_style"],
        expected["mobile_style"],
        "data-header-search-toggle",
        "data-header-search-popover",
    )
    for marker in required_index:
        if marker not in index:
            raise SystemExit(f"Local index is missing: {marker}")

    for marker in (expected["header_module"], expected["mobile_module"], "public-presentation-guard.js"):
        if marker not in pwa:
            raise SystemExit(f"Local pwa.js is missing: {marker}")

    for marker in (
        "./release-version.js",
        expected["header_style"],
        expected["mobile_style"],
        expected["header_module"],
        expected["mobile_module"],
        "public-presentation-guard.js",
        "public-presentation-rules.mjs",
    ):
        if marker not in worker:
            raise SystemExit(f"Local service worker is missing: {marker}")

    print(f"LOCAL_PWA_SHELL_OK release=v{release_number()}")


def fetch(path: str, timeout: int = 12) -> str:
    sep = "&" if "?" in path else "?"
    url = BASE + path + sep + "smoke=" + uuid.uuid4().hex
    request = urllib.request.Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "vivamos-production-smoke/2",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed public HTTPS origin
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read().decode("utf-8", errors="replace")


def wait_for_release(expected: int, attempts: int = 30, interval: int = 10) -> None:
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            published_source = fetch("release-version.js")
            match = re.search(r"const RELEASE = (\d+);", published_source)
            published = int(match.group(1)) if match else -1
            last = f"published v{published}, expected v{expected}"
            if published == expected:
                return
        except Exception as exc:  # production may be between deployments
            last = str(exc)
        if attempt == attempts:
            raise SystemExit(f"GitHub Pages did not publish the expected release: {last}")
        time.sleep(interval)


def verify_http() -> None:
    expected_release = release_number()
    expected = expected_shell()
    wait_for_release(expected_release)

    index = fetch("")
    pwa = fetch("pwa.js")
    worker = fetch("service-worker.js")

    for marker in (
        '<script src="./release-version.js"></script>',
        expected["header_style"],
        expected["mobile_style"],
        "data-header-search-toggle",
        "data-header-search-popover",
    ):
        if marker not in index:
            raise SystemExit(f"Published index is missing current shell marker: {marker}")

    for marker in (expected["header_module"], expected["mobile_module"], "public-presentation-guard.js"):
        if marker not in pwa:
            raise SystemExit(f"Published pwa.js is missing current shell marker: {marker}")

    for marker in (
        expected["header_style"],
        expected["mobile_style"],
        expected["header_module"],
        expected["mobile_module"],
        "public-presentation-guard.js",
        "public-presentation-rules.mjs",
    ):
        if marker not in worker:
            raise SystemExit(f"Published service worker is missing current shell marker: {marker}")

    print(f"PUBLISHED_PWA_SHELL_OK release=v{expected_release}")


def browser_binaries() -> list[str]:
    candidates: list[str] = []

    if os.name == "nt":
        env = os.environ
        roots = (
            env.get("ProgramFiles"),
            env.get("ProgramFiles(x86)"),
            env.get("LOCALAPPDATA"),
        )
        relative_paths = (
            r"Microsoft\Edge\Application\msedge.exe",
            r"Google\Chrome\Application\chrome.exe",
        )
        for root in roots:
            if not root:
                continue
            for relative in relative_paths:
                candidate = str(Path(root) / relative)
                if Path(candidate).is_file() and candidate not in candidates:
                    candidates.append(candidate)

    for name in (
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
        "microsoft-edge-stable",
    ):
        candidate = shutil.which(name)
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    if not candidates:
        raise SystemExit("Chrome/Chromium/Edge is unavailable on this machine")
    return candidates


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except Exception:
            process.kill()
    else:
        process.kill()


class _WebSocket:
    def __init__(self, url: str, timeout: float = 10.0) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "ws" or not parsed.hostname:
            raise RuntimeError(f"Unsupported DevTools WebSocket URL: {url}")

        port = parsed.port or 80
        self.sock = socket.create_connection((parsed.hostname, port), timeout=timeout)
        self.sock.settimeout(timeout)

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Origin: http://localhost\r\n"
            "\r\n"
        )
        self.sock.sendall(request.encode("ascii"))

        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(response) > 32768:
                break
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError(f"DevTools WebSocket handshake failed: {response[:300]!r}")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def _recv_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise EOFError("DevTools WebSocket closed")
            data += chunk
        return data

    def send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        mask = os.urandom(4)
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        header.extend(bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload)))
        self.sock.sendall(header)

    def receive_text(self) -> str:
        fragments = bytearray()
        collecting_text = False
        while True:
            first, second = self._recv_exact(2)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            length = second & 0x7F
            masked = bool(second & 0x80)

            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]

            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length)
            if masked:
                payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))

            if opcode == 0x9:  # ping
                pong = bytes([0x8A, len(payload)]) + payload
                self.sock.sendall(pong)
                continue
            if opcode == 0x8:
                raise EOFError("DevTools WebSocket closed")
            if opcode == 0x1:
                fragments.extend(payload)
                collecting_text = True
                if final:
                    return fragments.decode("utf-8", errors="replace")
                continue
            if opcode == 0x0 and collecting_text:
                fragments.extend(payload)
                if final:
                    return fragments.decode("utf-8", errors="replace")


def _cdp_command(
    websocket: _WebSocket,
    command_id: int,
    method: str,
    params: dict[str, object] | None = None,
    timeout: float = 15.0,
) -> dict[str, object]:
    websocket.send_text(
        json.dumps(
            {
                "id": command_id,
                "method": method,
                "params": params or {},
            }
        )
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        websocket.sock.settimeout(max(0.1, deadline - time.monotonic()))
        message = json.loads(websocket.receive_text())
        if message.get("id") != command_id:
            continue
        if "error" in message:
            raise RuntimeError(f"DevTools {method} failed: {message['error']}")
        result = message.get("result")
        return result if isinstance(result, dict) else {}
    raise TimeoutError(f"DevTools command timed out: {method}")


def _windows_cdp_dom(browser: str, city: str, width: int, height: int) -> str:
    profile = tempfile.mkdtemp(prefix=f"vivamos-prod-{city}-")
    try:
        cmd = [
            browser,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-background-mode",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-notifications",
            "--disable-component-extensions-with-background-pages",
            "--disable-crash-reporter",
            "--disable-breakpad",
            "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication,PushMessaging,NotificationTriggers",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            "--log-level=3",
            f"--window-size={width},{height}",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "about:blank",
        ]

        process = subprocess.Popen(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        websocket: _WebSocket | None = None
        try:
            devtools_file = Path(profile) / "DevToolsActivePort"
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if devtools_file.is_file():
                    break
                if process.poll() is not None:
                    error = process.stderr.read()[-1800:] if process.stderr else ""
                    raise RuntimeError(f"browser exited before DevTools was ready: {error}")
                time.sleep(0.1)
            if not devtools_file.is_file():
                raise TimeoutError("DevToolsActivePort was not created")

            lines = devtools_file.read_text(encoding="utf-8").splitlines()
            if not lines:
                raise RuntimeError("DevToolsActivePort is empty")
            port = int(lines[0])

            target_request = urllib.request.Request(
                f"http://127.0.0.1:{port}/json/new",
                method="PUT",
            )
            with urllib.request.urlopen(target_request, timeout=8) as response:  # nosec B310 - loopback only
                target = json.load(response)
            websocket_url = target.get("webSocketDebuggerUrl")
            if not isinstance(websocket_url, str):
                raise RuntimeError("DevTools target has no WebSocket URL")

            websocket = _WebSocket(websocket_url)
            _cdp_command(websocket, 1, "Page.enable")
            _cdp_command(websocket, 2, "Runtime.enable")

            url = f"{BASE}?city={city}&smoke={uuid.uuid4().hex}"
            navigation = _cdp_command(
                websocket,
                3,
                "Page.navigate",
                {"url": url},
                timeout=15,
            )
            error_text = navigation.get("errorText")
            if error_text:
                raise RuntimeError(f"Page.navigate failed: {error_text}")

            expression = r"""
new Promise(resolve => {
  const deadline = Date.now() + 20000;
  const ready = () => {
    const hasCard = Boolean(document.querySelector(".event-card"));
    const searchBound = Boolean(document.querySelector('[data-header-search-bound="true"]'));
    const loading = document.body && document.body.innerText.includes("Preparando la agenda");
    return hasCard && searchBound && !loading;
  };
  const tick = () => {
    if (ready() || Date.now() >= deadline) {
      resolve(document.documentElement.outerHTML);
      return;
    }
    setTimeout(tick, 200);
  };
  tick();
})
"""
            evaluated = _cdp_command(
                websocket,
                4,
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "awaitPromise": True,
                    "returnByValue": True,
                },
                timeout=30,
            )
            result = evaluated.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("Runtime.evaluate returned no result")
            dom = result.get("value")
            if not isinstance(dom, str) or "<html" not in dom.lower():
                raise RuntimeError("Runtime.evaluate returned no HTML document")
            return dom
        finally:
            if websocket is not None:
                websocket.close()
            _kill_process_tree(process)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def _dump_dom(browser: str, city: str, width: int, height: int) -> str:
    last_error = ""
    for attempt in range(1, 3):
        with tempfile.TemporaryDirectory(prefix=f"vivamos-prod-{city}-") as profile:
            url = f"{BASE}?city={city}&smoke={uuid.uuid4().hex}"
            cmd = [
                browser,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-sync",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
                "--disable-features=MediaRouter,OptimizationHints,AutofillServerCommunication",
                "--metrics-recording-only",
                "--no-first-run",
                "--no-default-browser-check",
                f"--window-size={width},{height}",
                "--virtual-time-budget=10000",
                f"--user-data-dir={profile}",
                "--dump-dom",
                url,
            ]
            result = subprocess.run(cmd, text=True, capture_output=True, timeout=40)
            if result.returncode == 0 and result.stdout:
                return result.stdout
            last_error = result.stderr[-1600:] or f"Chrome exit code {result.returncode} with empty DOM"
            if attempt < 2:
                time.sleep(2)
    raise RuntimeError(f"Chrome failed for {city} {width}x{height} after retry: {last_error}")


def cold_dom(browsers: list[str], city: str, width: int, height: int) -> str:
    errors: list[str] = []

    if os.name == "nt":
        for browser in browsers:
            try:
                return _windows_cdp_dom(browser, city, width, height)
            except Exception as exc:
                errors.append(f"{Path(browser).name}: {exc}")
        detail = " | ".join(errors[-4:])
        raise SystemExit(f"Windows browser failed for {city} {width}x{height} after retry: {detail}")

    for browser in browsers:
        try:
            return _dump_dom(browser, city, width, height)
        except Exception as exc:
            errors.append(f"{Path(browser).name}: {exc}")
    detail = " | ".join(errors[-4:])
    raise SystemExit(f"Browser failed for {city} {width}x{height} after retry: {detail}")


def verify_browser() -> None:
    expected_release = release_number()
    expected = expected_shell()
    browsers = browser_binaries()
    browser_header_style = expected["header_style"].removeprefix("./")
    browser_mobile_style = expected["mobile_style"].removeprefix("./")
    cases = (
        ("valparaiso", "Valparaíso / Viña del Mar", 390, 844),
        ("gijon", "Gijón / Xixón", 1280, 900),
    )
    for city, label, width, height in cases:
        dom = cold_dom(browsers, city, width, height)
        checks = {
            f'data-city="{city}"': "active city was not applied",
            "data-header-redesign=": "header markup disappeared",
            'data-header-search-bound="true"': "static search control was not bound",
            f"PWA v{expected_release}": "visible runtime version is stale",
            label: "city title/label is stale",
            browser_mobile_style: "mobile stylesheet revision is stale",
            browser_header_style: "header stylesheet revision is stale",
        }
        for marker, message in checks.items():
            if marker not in dom:
                raise SystemExit(f"{message}: {city} {width}x{height}")
        if dom.count('class="event-card') <= 0:
            raise SystemExit(f"No event cards rendered: {city} {width}x{height}")
        status = re.search(r"data-status[^>]*>(.*?)</", dom, flags=re.S)
        if status and "Preparando la agenda" in html.unescape(re.sub(r"<[^>]+>", "", status.group(1))):
            raise SystemExit(f"Production stayed in loading state: {city} {width}x{height}")
        print(f"PRODUCTION_COLD_LOAD_OK city={city} viewport={width}x{height}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the local or published ¡Vivamos! PWA shell.")
    parser.add_argument("mode", choices=("local", "http", "browser", "all"))
    args = parser.parse_args()
    if args.mode in {"local", "all"}:
        local_contract()
    if args.mode in {"http", "all"}:
        verify_http()
    if args.mode in {"browser", "all"}:
        verify_browser()


if __name__ == "__main__":
    main()
