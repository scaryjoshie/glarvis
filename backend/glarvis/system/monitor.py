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
    from glarvis.system.windows import get_clipboard_text, get_foreground_hwnd, get_visible_windows
else:
    raise ImportError(f"SystemMonitor not supported on {sys.platform}")


@dataclass
class WindowInfo:
    """A visible window with a stable integer ID for LLM use."""
    id: int               # stable integer (1, 2, 3...)
    title: str
    hwnd: int             # native handle (internal, not exposed to LLM)
    pid: int


@dataclass
class SystemState:
    """Snapshot of current system state."""
    windows: list[WindowInfo] = field(default_factory=list)
    foreground_id: int | None = None      # WindowInfo.id of focused window
    clipboard: str | None = None
    time: str = ""                         # human-readable time string

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
                lines.append(f"  [{w.id}] {w.title}{marker}")
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

    def start(self):
        """Start the background polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"[SystemMonitor] Started (interval={self.interval}s)")

    def stop(self):
        """Stop the background polling loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("[SystemMonitor] Stopped")

    async def _loop(self):
        """Poll system state on interval."""
        while self._running:
            try:
                self._update()
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
                hwnd=hwnd,
                pid=w["pid"],
            ))

        # Clean up stale entries
        stale = [h for h in self._hwnd_to_id if h not in seen_hwnds]
        for h in stale:
            del self._hwnd_to_id[h]

        self.state.windows = windows
        self.state.foreground_id = self._hwnd_to_id.get(fg_hwnd) if fg_hwnd else None

        # Clipboard
        self.state.clipboard = get_clipboard_text()
