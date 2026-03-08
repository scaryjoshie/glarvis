"""Windows-specific system queries using pywin32.

This module is the only place that imports win32 APIs. Swap this file
to support another platform.
"""

from __future__ import annotations

import base64
import ctypes
import io
import json
import os
import struct
import subprocess
from pathlib import Path

import win32clipboard
import win32con
import win32gui
import win32process
import win32ui

# Windows titles that are system noise, not real user windows
_NOISE_TITLES = {
    "shell handwriting canvas",
    "windows input experience",
    "program manager",
    "msctfime ui",
    "default ime",
    "popuphost",
}


def _get_process_info(pid: int) -> tuple[str | None, str | None]:
    """Get (exe_name, exe_path) for a process ID."""
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None, None
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_uint(260)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                p = Path(buf.value)
                return p.stem.lower(), str(p)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass
    return None, None


def get_exe_icon(exe_path: str, size: int = 32) -> str | None:
    """Extract the icon from an exe as a base64-encoded PNG string."""
    try:
        from PIL import Image

        large, small = win32gui.ExtractIconEx(exe_path, 0)
        if not large:
            return None
        hicon = large[0]
        for h in large[1:] + list(small):
            win32gui.DestroyIcon(h)

        # Create a 32-bit DIB section for proper alpha
        bmi = struct.pack(
            "IiiHHIIIIII",
            40,       # biSize
            size,     # biWidth
            -size,    # biHeight (negative = top-down)
            1,        # biPlanes
            32,       # biBitCount
            0,        # biCompression (BI_RGB)
            0, 0, 0, 0, 0,
        )
        screen_hdc = win32gui.GetDC(0)
        mem_dc = win32ui.CreateDCFromHandle(screen_hdc).CreateCompatibleDC()

        hbmp = ctypes.windll.gdi32.CreateDIBSection(
            mem_dc.GetSafeHdc(), bmi, 0,  # DIB_RGB_COLORS
            ctypes.byref(ctypes.c_void_p()), None, 0,
        )
        old = win32gui.SelectObject(mem_dc.GetSafeHdc(), hbmp)

        # Draw icon with alpha blending
        win32gui.DrawIconEx(
            mem_dc.GetSafeHdc(), 0, 0, hicon, size, size,
            0, None, win32con.DI_NORMAL,
        )

        # Read raw BGRA pixels from DIB
        buf_size = size * size * 4
        raw = ctypes.create_string_buffer(buf_size)
        ctypes.windll.gdi32.GetBitmapBits(hbmp, buf_size, raw)

        # Cleanup GDI
        win32gui.SelectObject(mem_dc.GetSafeHdc(), old)
        ctypes.windll.gdi32.DeleteObject(hbmp)
        mem_dc.DeleteDC()
        win32gui.ReleaseDC(0, screen_hdc)
        win32gui.DestroyIcon(hicon)

        img = Image.frombuffer("RGBA", (size, size), raw, "raw", "BGRA", 0, 1)

        out = io.BytesIO()
        img.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode()
    except Exception:
        return None


def get_visible_windows() -> list[dict]:
    """Return list of visible windows with title, hwnd, pid, and app name.

    Each dict has: hwnd (int), title (str), pid (int), app (str).
    Filters out system noise windows and empty titles.
    """
    results = []

    def _enum_cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title or title.lower() in _NOISE_TITLES:
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        app, exe_path = _get_process_info(pid)
        results.append({"hwnd": hwnd, "title": title, "pid": pid, "app": app or "", "exe_path": exe_path})

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


def focus_window(hwnd: int) -> bool:
    """Bring a window to the foreground by hwnd. Returns True on success."""
    try:
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Attach to the foreground window's thread so Windows allows the switch
        fg_hwnd = win32gui.GetForegroundWindow()
        fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, None)
        our_thread = ctypes.windll.kernel32.GetCurrentThreadId()

        if fg_thread != our_thread:
            ctypes.windll.user32.AttachThreadInput(our_thread, fg_thread, True)

        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)

        if fg_thread != our_thread:
            ctypes.windll.user32.AttachThreadInput(our_thread, fg_thread, False)

        return True
    except Exception:
        return False


def scan_start_apps() -> list[dict]:
    """Get installed apps using PowerShell Get-StartApps.

    Returns list of dicts: name (str), app_id (str).
    Names are the display names users see in the Start Menu.
    app_id can be used to launch via shell:AppsFolder.
    """
    _skip_names = [
        "uninstall", "readme", "help", "license", "changelog", "release notes",
        "documentation", "samples for", "tools for", "support center",
        "private browsing", "reset preferences", "command prompt",
        "module docs", "manuals", "faq", "website", "homepage",
        "verifier", "debuggable", "skinned", "stereo 3d",
    ]

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        apps = json.loads(result.stdout)
        if not isinstance(apps, list):
            apps = [apps]

        programs = []
        seen_names = set()
        for app in apps:
            name = app.get("Name", "").strip()
            app_id = app.get("AppID", "").strip()
            if not name or not app_id:
                continue
            name_lower = name.lower()
            if name_lower in seen_names:
                continue
            if any(skip in name_lower for skip in _skip_names):
                continue
            seen_names.add(name_lower)
            programs.append({"name": name, "app_id": app_id})

        programs.sort(key=lambda p: p["name"].lower())
        return programs
    except Exception:
        return []


def launch_app(app_id: str) -> bool:
    """Launch an app by its AppID (from Get-StartApps). Returns True on success."""
    try:
        os.startfile(f"shell:AppsFolder\\{app_id}")
        return True
    except Exception:
        return False
