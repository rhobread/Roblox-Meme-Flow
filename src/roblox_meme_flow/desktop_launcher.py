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

UI_CLOSE_GRACE_SECONDS = 4.0
BROWSER_EXIT_HEARTBEAT_TIMEOUT_SECONDS = 20.0
ORPHAN_STARTUP_GRACE_SECONDS = 25.0


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


def should_auto_shutdown(
    *,
    now: float,
    started_at: float,
    last_heartbeat: float,
    ui_closed_at: float | None,
    browser_exited: bool,
    has_running_jobs: bool,
) -> bool:
    """Decide whether the Studio background server should exit cleanly.

    Rules:
    - Never kill an active background job mid-render (protects spent credits).
    - If the UI explicitly signalled window close (`ui_closed_at`) and didn't reload within
      `UI_CLOSE_GRACE_SECONDS`, shut down immediately.
    - If the spawned Studio app browser process has exited and no UI heartbeat arrived for
      `BROWSER_EXIT_HEARTBEAT_TIMEOUT_SECONDS`, shut down immediately.
    - If no browser window is tracked and no heartbeat has arrived for > 30s after startup,
      shut down automatically so no orphan background server lingers.
    """
    if has_running_jobs:
        return False

    if ui_closed_at is not None and (now - ui_closed_at) >= UI_CLOSE_GRACE_SECONDS:
        return True

    if browser_exited:
        # Allow a short startup grace window for initial browser launch / profile handoff.
        if (now - started_at) >= ORPHAN_STARTUP_GRACE_SECONDS and (now - last_heartbeat) >= BROWSER_EXIT_HEARTBEAT_TIMEOUT_SECONDS:
            return True
        if (now - last_heartbeat) >= BROWSER_EXIT_HEARTBEAT_TIMEOUT_SECONDS and (now - started_at) >= 10.0:
            return True

    return False


def _terminate_own_descendants() -> None:
    """Cleanly terminate any leftover child processes spawned by this Studio process only.

    Specifically cleans up Studio's isolated browser crashpad-handler or stray child tools
    without ever touching the user's personal Brave/Edge/Chrome/VS Code processes.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        from roblox_meme_flow.win_silent import _get_descendant_pids

        own_pid = os.getpid()
        descendants = _get_descendant_pids(own_pid) - {own_pid}
        if not descendants:
            return
        kernel32 = ctypes.windll.kernel32
        PROCESS_TERMINATE = 0x0001
        for pid in descendants:
            handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                try:
                    kernel32.TerminateProcess(handle, 0)
                finally:
                    kernel32.CloseHandle(handle)
    except Exception:
        pass


def _maybe_stop_stale_server(url: str) -> None:
    """If an older Studio server is still listening on PORT, ask it to exit so new code loads."""
    import json

    from roblox_meme_flow.web_ui import compute_code_fingerprint

    expected = compute_code_fingerprint()
    try:
        with urllib.request.urlopen(f"{url}/api/status?refresh_credits=false", timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code_fingerprint") == expected:
            return
    except Exception:
        return

    try:
        req = urllib.request.Request(f"{url}/api/admin/restart-if-idle", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=2.0):
            pass
    except Exception:
        return

    deadline = time.time() + 5.0
    while time.time() < deadline:
        if not _is_port_open(HOST, PORT):
            return
        time.sleep(0.25)


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
    app = None

    if _is_port_open(HOST, PORT):
        _maybe_stop_stale_server(APP_URL)

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

    proc: subprocess.Popen[bytes] | None = None
    if browser:
        proc = subprocess.Popen(
            [
                browser,
                f"--app={APP_URL}",
                f"--user-data-dir={profile_dir}",
                "--window-size=1380,900",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-mode",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        import webbrowser

        webbrowser.open(APP_URL)

    if started_here and app is not None:
        try:
            while True:
                time.sleep(1.5)
                snap = app.state.lifecycle_snapshot()
                browser_exited = True if proc is None else (proc.poll() is not None)
                if getattr(app.state, "shutdown_requested", False) and not bool(snap["has_running_jobs"]):
                    print("[SHUTDOWN] Stale server replaced by newer Studio launch.", flush=True)
                    break
                if should_auto_shutdown(
                    now=time.monotonic(),
                    started_at=float(snap["started_at"]),
                    last_heartbeat=float(snap["last_heartbeat"]),
                    ui_closed_at=snap["ui_closed_at"],  # type: ignore[arg-type]
                    browser_exited=browser_exited,
                    has_running_jobs=bool(snap["has_running_jobs"]),
                ):
                    print("[SHUTDOWN] Studio window closed and idle; stopping background server.", flush=True)
                    break
        finally:
            if server is not None:
                server.should_exit = True
                time.sleep(0.4)
            _terminate_own_descendants()
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except Exception:
                pass
            os._exit(0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
