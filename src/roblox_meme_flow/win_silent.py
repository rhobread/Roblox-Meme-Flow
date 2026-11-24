from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
import time
from typing import Iterator

NO_WINDOW_FLAGS: int = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


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


@contextlib.contextmanager
def suppress_offscreen_chromium_focus() -> Iterator[None]:
    """Keep user's active window focused and hide off-screen gflow Chromium windows on Windows.

    gflow launches Chromium at (-30000, -30000) to satisfy reCAPTCHA Enterprise while staying
    off-screen, but Chromium still steals keyboard focus or shows on the taskbar at launch.
    This watcher ONLY hides top-level Chrome_WidgetWin_1 windows positioned off-screen (x < -10000)
    and restores the user's previous foreground window if focus was stolen.
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

    def _hide_offscreen_chrome() -> bool:
        hid_any = False

        def _cb(hwnd: int, _lparam: int) -> bool:
            nonlocal hid_any
            if not user32.IsWindowVisible(hwnd):
                return True
            cls_buf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, cls_buf, 128)
            if cls_buf.value != "Chrome_WidgetWin_1":
                return True
            rect = RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                # Strictly target gflow's off-screen (-30000, -30000) Chromium window only!
                if rect.left < -10000 or rect.top < -10000:
                    user32.ShowWindow(hwnd, SW_HIDE)
                    hid_any = True
            return True

        user32.EnumWindows(WNDENUMPROC(_cb), 0)
        return hid_any

    def _loop() -> None:
        while not stop_event.is_set():
            try:
                if _hide_offscreen_chrome() and prev_fg and user32.IsWindow(prev_fg):
                    cur_fg = user32.GetForegroundWindow()
                    if cur_fg != prev_fg:
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
