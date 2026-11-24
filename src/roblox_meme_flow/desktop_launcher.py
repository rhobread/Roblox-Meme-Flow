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


def _app_browser_running(profile_marker: str) -> bool:
    """Return True if any Chromium app-mode browser process using our profile is still running."""
    try:
        ps_cmd = (
            "Get-CimInstance Win32_Process | "
            f"Where-Object {{ $_.CommandLine -like '*{profile_marker}*' }} | "
            "Measure-Object | Select-Object -ExpandProperty Count"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        return int(proc.stdout.strip() or "0") > 0
    except Exception:
        return True


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent.parent
    os.chdir(project_root)

    # Under pythonw.exe on Windows, sys.stdout/sys.stderr are None, which crashes uvicorn's
    # default TTY log formatter. Redirect both to a local log file and disable TTY log_config.
    log_file = project_root / "outputs" / "desktop_launcher.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None or sys.stderr is None:
        fh = open(log_file, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = fh
        if sys.stderr is None:
            sys.stderr = fh

    try:
        from roblox_meme_flow.win_silent import restore_hidden_user_chromium_windows

        restored = restore_hidden_user_chromium_windows()
        if restored:
            print(f"[RECOVERY] Restored {restored} hidden user window(s) back to taskbar.", flush=True)
    except Exception:
        pass

    started_here = False
    server = None

    if not _is_port_open(HOST, PORT):
        import uvicorn

        from roblox_meme_flow.web_ui import create_app

        app = create_app(project_root)
        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_config=None,
            access_log=False,
        )
        server = uvicorn.Server(config)
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
        if started_here:
            # Wait for initial process, then keep server alive while any window with our
            # dedicated .studio_app_profile remains open (handles Brave/Chrome handoff).
            proc.wait()
            time.sleep(2.0)
            while _app_browser_running(".studio_app_profile"):
                time.sleep(2.5)
            if server is not None:
                server.should_exit = True
                time.sleep(0.3)
    else:
        import webbrowser

        webbrowser.open(APP_URL)
        if started_here:
            while True:
                time.sleep(1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
