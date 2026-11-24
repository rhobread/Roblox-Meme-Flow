from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8787
APP_URL = f"http://{HOST}:{PORT}"


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _wait_for_server(url: str, timeout_s: float = 12.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/status?refresh_credits=false", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def _find_app_browser() -> str | None:
    candidates = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent.parent
    os.chdir(project_root)

    started_here = False
    server = None

    if not _is_port_open(HOST, PORT):
        import uvicorn

        from roblox_meme_flow.web_ui import create_app

        app = create_app(project_root)
        config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning", access_log=False)
        server = uvicorn.Server(config)
        # Prevent uvicorn from installing signal handlers in non-main thread
        server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        started_here = True

        if not _wait_for_server(APP_URL, timeout_s=15.0):
            return 1

    browser = _find_app_browser()
    profile_dir = project_root / "outputs" / ".studio_app_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    if browser:
        proc = subprocess.Popen(
            [
                browser,
                f"--app={APP_URL}",
                f"--user-data-dir={profile_dir}",
                "--window-size=1380,900",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait until user closes the desktop app window, then cleanly stop local backend
        if started_here:
            proc.wait()
            if server is not None:
                server.should_exit = True
                time.sleep(0.3)
    else:
        import webbrowser

        webbrowser.open(APP_URL)
        if started_here:
            # Keep server alive until killed if no Chromium app-mode browser is found
            while True:
                time.sleep(1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
