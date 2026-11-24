from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
from typing import Iterator

NO_WINDOW_FLAGS: int = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

_USER_CHROMIUM_EXES = frozenset({"code.exe", "msedge.exe", "brave.exe", "chrome.exe"})


def silent_subprocess_kwargs() -> dict[str, object]:
    """Return subprocess kwargs that suppress CMD/console popups on Windows."""
    if sys.platform != "win32":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return {
        "creationflags": NO_WINDOW_FLAGS,
        "startupinfo": si,
    }


def is_gflow_playwright_executable(exe_path: str) -> bool:
    """Return True ONLY for Playwright's bundled Chromium executable used by gflow.

    Explicitly rejects user browsers and Electron apps (VS Code, Edge, Brave, Chrome, etc.).
    """
    norm = exe_path.replace("/", "\\").strip().lower()
    if "\\ms-playwright\\" not in norm:
        return False
    basename = norm.rsplit("\\", 1)[-1]
    return basename in {"chrome.exe", "chromium.exe", "chrome-headless-shell.exe"}


def should_hide_gflow_window(
    *,
    class_name: str,
    is_visible: bool,
    is_iconic: bool,
    rect_left: int,
    rect_top: int,
    exe_path: str,
    pid: int,
    allowed_pids: set[int] | None,
) -> bool:
    """Strictly decide whether a Win32 window is gflow's off-screen Playwright Chromium window.

    Safety invariants:
    - Never touches minimized windows (IsIconic == True), because Windows positions ALL minimized
      windows at (-32000, -32000).
    - Never touches any process outside Playwright's bundled ms-playwright Chromium executable.
    - When `allowed_pids` is provided, only touches processes in the spawned gflow PID tree.
    """
    if not is_visible or is_iconic:
        return False
    if class_name != "Chrome_WidgetWin_1":
        return False
    if not is_gflow_playwright_executable(exe_path):
        return False
    if allowed_pids is not None and pid not in allowed_pids:
        return False
    return rect_left <= -20000 or rect_top <= -20000


def _query_process_image_path(pid: int) -> str:
    if sys.platform != "win32" or pid <= 0:
        return ""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _get_descendant_pids(root_pid: int) -> set[int]:
    """Return `root_pid` and all descendant PIDs via Win32 Toolhelp snapshot."""
    if sys.platform != "win32" or root_pid <= 0:
        return set()
    import ctypes
    from ctypes import wintypes

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    MAX_PATH = 260

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * MAX_PATH),
        ]

    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE or not snap:
        return {root_pid}

    children_map: dict[int, list[int]] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                children_map.setdefault(int(entry.th32ParentProcessID), []).append(int(entry.th32ProcessID))
                if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snap)

    result: set[int] = set()
    stack = [root_pid]
    while stack:
        cur = stack.pop()
        if cur in result:
            continue
        result.add(cur)
        stack.extend(children_map.get(cur, ()))
    return result


def restore_hidden_user_chromium_windows() -> int:
    """Restore any user VS Code / Edge / Brave / Chrome windows that were hidden while minimized.

    Returns the number of windows restored back onto the taskbar (without stealing focus).
    """
    if sys.platform != "win32":
        return 0

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    SW_SHOWMINNOACTIVE = 7
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    restored = 0

    def _cb(hwnd: int, _lparam: int) -> bool:
        nonlocal restored
        if user32.IsWindowVisible(hwnd):
            return True
        if not user32.IsIconic(hwnd):
            return True
        cls_buf = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, cls_buf, 128)
        if cls_buf.value != "Chrome_WidgetWin_1":
            return True
        if user32.GetWindowTextLengthW(hwnd) <= 0:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe_path = _query_process_image_path(int(pid.value))
        if not exe_path or is_gflow_playwright_executable(exe_path):
            return True
        basename = exe_path.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        if basename in _USER_CHROMIUM_EXES:
            user32.ShowWindow(hwnd, SW_SHOWMINNOACTIVE)
            restored += 1
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return restored


@contextlib.contextmanager
def suppress_offscreen_chromium_focus(root_pid: int | None = None) -> Iterator[None]:
    """Hide ONLY gflow's own off-screen Playwright Chromium window without affecting user apps.

    Safety guarantees:
    - Strictly checks `not IsIconic(hwnd)` (never touches minimized apps).
    - Strictly checks `is_gflow_playwright_executable(exe_path)` (`\\ms-playwright\\` only).
    - When `root_pid` is provided, strictly checks that the window belongs to a descendant PID of `root_pid`.
    - Only restores previous foreground focus if the current foreground window belongs to gflow's Playwright process.
    """
    if sys.platform != "win32":
        yield
        return

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    SW_HIDE = 0

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    prev_fg = user32.GetForegroundWindow()
    stop_event = threading.Event()
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _hide_offscreen_gflow_chrome() -> tuple[bool, set[int] | None]:
        hid_any = False
        allowed_pids = _get_descendant_pids(root_pid) if root_pid else None

        def _cb(hwnd: int, _lparam: int) -> bool:
            nonlocal hid_any
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            cls_buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, cls_buf, 128)
            if cls_buf.value != "Chrome_WidgetWin_1":
                return True
            pid_val = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_val))
            pid = int(pid_val.value)
            if allowed_pids is not None and pid not in allowed_pids:
                return True
            exe_path = _query_process_image_path(pid)
            rect = RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
            if should_hide_gflow_window(
                class_name=cls_buf.value,
                is_visible=True,
                is_iconic=False,
                rect_left=int(rect.left),
                rect_top=int(rect.top),
                exe_path=exe_path,
                pid=pid,
                allowed_pids=allowed_pids,
            ):
                user32.ShowWindow(hwnd, SW_HIDE)
                hid_any = True
            return True

        user32.EnumWindows(WNDENUMPROC(_cb), 0)
        return hid_any, allowed_pids

    def _loop() -> None:
        while not stop_event.is_set():
            try:
                hid_any, allowed_pids = _hide_offscreen_gflow_chrome()
                if hid_any and prev_fg and user32.IsWindow(prev_fg):
                    cur_fg = user32.GetForegroundWindow()
                    if cur_fg and cur_fg != prev_fg:
                        fg_pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(cur_fg, ctypes.byref(fg_pid))
                        fg_pid_int = int(fg_pid.value)
                        fg_exe = _query_process_image_path(fg_pid_int)
                        if is_gflow_playwright_executable(fg_exe) and (
                            allowed_pids is None or fg_pid_int in allowed_pids
                        ):
                            user32.SetForegroundWindow(prev_fg)
            except Exception:
                pass
            stop_event.wait(0.25)

    watcher = threading.Thread(target=_loop, daemon=True)
    watcher.start()
    try:
        yield
    finally:
        stop_event.set()
        watcher.join(timeout=1.0)


def run_silent_gflow_subprocess(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a gflow subprocess silently while scoping the window watcher strictly to its PID tree."""
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        **silent_subprocess_kwargs(),
    )
    with suppress_offscreen_chromium_focus(root_pid=proc.pid):
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            raise
    return subprocess.CompletedProcess(
        args=args,
        returncode=proc.returncode,
        stdout=stdout or "",
        stderr=stderr or "",
    )


if __name__ == "__main__":
    count = restore_hidden_user_chromium_windows()
    print(f"Restored {count} hidden window(s) back to the taskbar.")

