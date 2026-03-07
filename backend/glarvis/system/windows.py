"""Windows-specific system queries using pywin32.

This module is the only place that imports win32 APIs. Swap this file
to support another platform.
"""

from __future__ import annotations

import win32clipboard
import win32gui
import win32process


def get_visible_windows() -> list[dict]:
    """Return list of visible windows with title, hwnd, and pid.

    Each dict has: hwnd (int), title (str), pid (int).
    Filters out windows with empty titles and invisible windows.
    """
    results = []

    def _enum_cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        results.append({"hwnd": hwnd, "title": title, "pid": pid})

    win32gui.EnumWindows(_enum_cb, None)
    return results


def get_foreground_hwnd() -> int | None:
    """Return the hwnd of the foreground window, or None."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        return hwnd if hwnd else None
    except Exception:
        return None


def get_clipboard_text() -> str | None:
    """Return clipboard text content, or None if unavailable."""
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                return data
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass
    return None
