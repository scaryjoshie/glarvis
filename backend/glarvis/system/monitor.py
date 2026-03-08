"""SystemMonitor — background loop that maintains live system state.

Platform-agnostic interface. The actual system queries are in windows.py
(or a future linux.py / mac.py).
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

# Import platform-specific backend
if sys.platform == "win32":
    from glarvis.system.windows import (
        focus_window as _focus_window,
        get_clipboard_text,
        get_exe_icon,
        get_foreground_hwnd,
        get_visible_windows,
        launch_app as _launch_app,
        scan_start_apps,
    )
else:
    raise ImportError(f"SystemMonitor not supported on {sys.platform}")


@dataclass
class ProgramInfo:
    """An installed program from the Start Menu."""
    name: str
    app_id: str


@dataclass
class WindowInfo:
    """A visible window with a stable integer ID for LLM use."""
    id: int               # stable integer (1, 2, 3...)
    title: str
    app: str              # process name (e.g. "notepad", "code", "chrome")
    hwnd: int             # native handle (internal, not exposed to LLM)
    pid: int
    exe_path: str | None = None  # full path to the executable


@dataclass
class SystemState:
    """Snapshot of current system state."""
    windows: list[WindowInfo] = field(default_factory=list)
    foreground_id: int | None = None # WindowInfo.id of focused window
    clipboard: str | None = None
    time: str = "" # human-readable time string

    def summary(self) -> str:
        """Compact text summary for LLM system message injection."""
        lines = []

        # Time
        lines.append(f"Time: {self.time}")

        # Windows
        if self.windows:
            lines.append(f"Windows ({len(self.windows)}):")
            for w in self.windows:
                marker = " *" if w.id == self.foreground_id else ""
                app_tag = f" ({w.app})" if w.app else ""
                lines.append(f"  [{w.id}] {w.title}{app_tag}{marker}")
            if self.foreground_id is not None:
                fg = next((w for w in self.windows if w.id == self.foreground_id), None)
                if fg:
                    lines.append(f"Focused: [{fg.id}] {fg.title}")
        else:
            lines.append("Windows: none detected")

        # Clipboard (truncated)
        if self.clipboard:
            preview = self.clipboard[:100]
            if len(self.clipboard) > 100:
                preview += "..."
            lines.append(f"Clipboard: {preview}")

        return "\n".join(lines)


class SystemMonitor:
    """Background monitor that polls system state on an interval.

    Usage:
        monitor = SystemMonitor(interval=2.0)
        monitor.start()       # begins background polling
        state = monitor.state # current SystemState snapshot
        monitor.stop()        # clean shutdown
    """

    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.state = SystemState()
        self._task: asyncio.Task | None = None
        self._running = False

        # Stable ID mapping: hwnd → integer ID
        self._hwnd_to_id: dict[int, int] = {}
        self._next_id = 1

        # Installed programs (scanned once on start)
        self.programs: list[ProgramInfo] = []

        # Icon cache: exe_path → base64 PNG (or None for failed extractions)
        self._icon_cache: dict[str, str | None] = {}

    def start(self):
        """Start the background polling loop."""
        if self._running:
            return
        self._running = True
        self._scan_programs()
        try:
            self._update()
        except Exception as e:
            logger.error(f"[SystemMonitor] Initial update failed: {e}")
        self._task = asyncio.create_task(self._loop())
        logger.info(f"[SystemMonitor] Started (interval={self.interval}s, {len(self.programs)} programs, {len(self.state.windows)} windows)")

    def _scan_programs(self):
        """Scan installed apps via Get-StartApps (once on start)."""
        try:
            raw = scan_start_apps()
            self.programs = [ProgramInfo(name=p["name"], app_id=p["app_id"]) for p in raw]
        except Exception as e:
            logger.error(f"[SystemMonitor] Program scan failed: {e}")
            self.programs = []

    def stop(self):
        """Stop the background polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[SystemMonitor] Stopped")

    async def _loop(self):
        """Poll system state on interval."""
        tick = 0
        while self._running:
            try:
                self._update()
                tick += 1
                if tick <= 3 or tick % 30 == 0:  # log first 3 ticks, then every 60s
                    fg = next((w for w in self.state.windows if w.id == self.state.foreground_id), None)
                    fg_title = fg.title[:40] if fg else "none"
                    logger.debug(f"[SystemMonitor] tick={tick} windows={len(self.state.windows)} fg={fg_title}")
            except Exception as e:
                logger.error(f"[SystemMonitor] Update error: {e}")
            await asyncio.sleep(self.interval)

    def _update(self):
        """Refresh system state from platform APIs."""
        # Time
        self.state.time = datetime.now().strftime("%I:%M %p, %A %B %d")

        # Windows
        raw_windows = get_visible_windows()
        fg_hwnd = get_foreground_hwnd()

        # Build/reuse stable IDs
        seen_hwnds = set()
        windows = []
        for w in raw_windows:
            hwnd = w["hwnd"]
            seen_hwnds.add(hwnd)
            if hwnd not in self._hwnd_to_id:
                self._hwnd_to_id[hwnd] = self._next_id
                self._next_id += 1
            wid = self._hwnd_to_id[hwnd]
            windows.append(WindowInfo(
                id=wid,
                title=w["title"],
                app=w.get("app", ""),
                hwnd=hwnd,
                pid=w["pid"],
                exe_path=w.get("exe_path"),
            ))

        # Clean up stale entries
        stale = [h for h in self._hwnd_to_id if h not in seen_hwnds]
        for h in stale:
            del self._hwnd_to_id[h]

        self.state.windows = windows
        self.state.foreground_id = self._hwnd_to_id.get(fg_hwnd) if fg_hwnd else None

        # Clipboard
        self.state.clipboard = get_clipboard_text()

    # ── Actions ──────────────────────────────────────────────────────────

    def focus_window(self, window_id: int) -> bool:
        """Focus a window by its stable integer ID. Returns True on success."""
        win = next((w for w in self.state.windows if w.id == window_id), None)
        if not win:
            return False
        return _focus_window(win.hwnd)

    def launch_program(self, app_id: str) -> bool:
        """Launch a program by its AppID. Returns True on success."""
        return _launch_app(app_id)

    def get_window_icon(self, window_id: int) -> str | None:
        """Get base64 PNG icon for a window by its stable ID. Cached by exe path."""
        win = next((w for w in self.state.windows if w.id == window_id), None)
        if not win or not win.exe_path:
            return None
        if win.exe_path not in self._icon_cache:
            self._icon_cache[win.exe_path] = get_exe_icon(win.exe_path)
        return self._icon_cache[win.exe_path]

    def search_programs(self, query: str) -> list[ProgramInfo]:
        """Fuzzy search installed programs by name."""
        q = query.lower()
        return [p for p in self.programs if q in p.name.lower()]
