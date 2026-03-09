"""Terminal — app-specific context for Windows Terminal.

Auto-activates when Windows Terminal gains focus. Provides:
- Tab switching via left/right voice intercepts (Ctrl+Shift+Tab / Ctrl+Tab)
- Directory bookmarks (named paths, navigable via multi-choice popup)
- "bookmark" to save current directory, "bookmarks" to navigate
"""

from __future__ import annotations

import asyncio
import re

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema

from glarvis.tool import AppSessionTool, Intercept, Keyword, TaskResult


# Virtual key codes
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_TAB = 0x09
VK_RETURN = 0x0D

# Patterns for extracting current directory from terminal window titles
# MINGW64:/c/Users/... | MSYS:/c/... | usr/bin/bash - /c/Users/...
_MINGW_PATH = re.compile(r"MINGW\d*:(/\S+)|MSYS:(/\S+)")
# C:\Users\... anywhere in the title
_WIN_PATH = re.compile(r"([A-Z]:\\[^\s*]+)")
# /c/Users/... style (git bash without MINGW prefix, e.g. in tab title)
_UNIX_PATH = re.compile(r"(/[a-z]/\S+)")


class TerminalSession(AppSessionTool):
    name = "terminal"
    description = "Terminal context with tab switching and directory bookmarks."
    parameters = {}
    required = []
    app_name = "windowsterminal"
    persist_in_display = True
    cancel_on_interruption = False

    async def run(self, **kwargs) -> TaskResult:
        self._done_event = asyncio.Event()
        self._load_bookmarks()
        logger.info(f"[Terminal] Session started with {len(self._bookmarks)} bookmarks")
        await self._done_event.wait()
        return TaskResult(result="Terminal session ended.")

    def _load_bookmarks(self):
        from glarvis.settings import load_settings
        self._bookmarks = dict(load_settings().terminal.bookmarks)

    def _save_bookmarks(self):
        from glarvis.settings import load_settings, save_settings
        settings = load_settings()
        settings.terminal.bookmarks = dict(self._bookmarks)
        save_settings(settings)

    # ── Current directory detection ───────────────────────────────────────

    def _get_current_directory(self) -> str | None:
        """Try to extract the current directory from the terminal's window title."""
        if not self.system:
            return None
        fg_id = self.system.state.foreground_id
        if fg_id is None:
            return None
        win = next((w for w in self.system.state.windows if w.id == fg_id), None)
        if not win or win.app != self.app_name:
            return None

        title = win.title

        # Try MINGW/MSYS style: MINGW64:/c/Users/...
        m = _MINGW_PATH.search(title)
        if m:
            path = m.group(1) or m.group(2)
            return self._unix_to_win_path(path)

        # Try Windows style: C:\Users\...
        m = _WIN_PATH.search(title)
        if m:
            return m.group(1).rstrip("*").strip()

        # Try bare unix style: /c/Users/...
        m = _UNIX_PATH.search(title)
        if m:
            return self._unix_to_win_path(m.group(1))

        return None

    @staticmethod
    def _unix_to_win_path(path: str) -> str:
        """Convert /c/Users/... to C:/Users/..."""
        if len(path) >= 3 and path[0] == "/" and path[2] == "/":
            return path[1].upper() + ":" + path[2:]
        return path

    # ── Context intercepts (active only when terminal focused) ────────────

    def get_context_intercepts(self) -> list[Intercept]:
        return [
            Keyword("left", self._tab_left),
            Keyword("right", self._tab_right),
            Keyword("previous tab", self._tab_left),
            Keyword("next tab", self._tab_right),
            Keyword("bookmark", self._bookmark_current),
            Keyword("bookmark this", self._bookmark_current),
            Keyword("save bookmark", self._bookmark_current),
            Keyword("bookmarks", self._show_bookmarks),
            Keyword("open bookmark", self._show_bookmarks),
            Keyword("open bookmarks", self._show_bookmarks),
            Keyword("go to", self._show_bookmarks),
        ]

    async def _tab_left(self) -> TaskResult:
        from glarvis.system.windows import send_key_combo
        send_key_combo(VK_CONTROL, VK_SHIFT, VK_TAB)
        logger.info("[Terminal] Tab left")
        return TaskResult(result="Switched to previous tab.")

    async def _tab_right(self) -> TaskResult:
        from glarvis.system.windows import send_key_combo
        send_key_combo(VK_CONTROL, VK_TAB)
        logger.info("[Terminal] Tab right")
        return TaskResult(result="Switched to next tab.")

    async def _bookmark_current(self) -> TaskResult:
        """Save the current terminal directory as a bookmark."""
        path = self._get_current_directory()
        if not path:
            return TaskResult(
                result="Could not detect current directory from terminal title.",
                guide="Can't detect the current directory.",
            )
        # Use the last folder name as the default bookmark name
        parts = path.replace("\\", "/").rstrip("/").split("/")
        name = parts[-1].lower() if parts else "unnamed"

        # Avoid duplicates by name
        if name in self._bookmarks and self._bookmarks[name] == path:
            return TaskResult(result=f"Bookmark '{name}' already exists.", guide=f"{name} is already bookmarked.")

        self._bookmarks[name] = path
        self._save_bookmarks()
        logger.info(f"[Terminal] Bookmarked current: {name} → {path}")
        return TaskResult(result=f"Bookmarked '{name}' → {path}", guide=f"Bookmarked as {name}.")

    async def _show_bookmarks(self) -> TaskResult:
        """Show a multi-choice popup with all bookmarks."""
        self._load_bookmarks()
        if not self._bookmarks:
            return TaskResult(result="No bookmarks saved.", guide="No bookmarks yet.")

        options = []
        for name, path in self._bookmarks.items():
            options.append({
                "text": f"{name}  —  {path}",
                "action": {"tool": "terminal_go_to", "args": {"name": name}},
            })

        await self.handle.execute_tool("show_choices", options=options, prompt="Bookmarks")
        return TaskResult(result="Bookmark selection shown.")

    # ── Context tools (available to LLM when terminal focused) ────────────

    def get_context_tools(self) -> list[FunctionSchema]:
        return [
            FunctionSchema(
                name="terminal_go_to",
                description="Navigate to a bookmarked directory by name.",
                properties={"name": {"type": "string", "description": "Bookmark name"}},
                required=["name"],
            ),
            FunctionSchema(
                name="terminal_bookmark",
                description="Save a directory bookmark. If no path given, bookmarks the current directory.",
                properties={
                    "name": {"type": "string", "description": "Bookmark name"},
                    "path": {"type": "string", "description": "Directory path (optional, defaults to current directory)"},
                },
                required=["name"],
            ),
            FunctionSchema(
                name="terminal_remove_bookmark",
                description="Remove a directory bookmark.",
                properties={"name": {"type": "string", "description": "Bookmark name"}},
                required=["name"],
            ),
            FunctionSchema(
                name="terminal_list_bookmarks",
                description="Show bookmarks as a multi-choice popup for navigation.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="terminal_run",
                description="Type a command into the terminal and press Enter.",
                properties={"command": {"type": "string", "description": "Command to run"}},
                required=["command"],
            ),
        ]

    async def handle_context_call(self, tool_name: str, **kwargs) -> TaskResult:
        if tool_name == "terminal_go_to":
            return await self._go_to(kwargs.get("name", ""))
        elif tool_name == "terminal_bookmark":
            name = kwargs.get("name", "")
            path = kwargs.get("path", "")
            if not path:
                # No path given — bookmark current directory
                detected = self._get_current_directory()
                if not detected:
                    return TaskResult(result="No path given and couldn't detect current directory.")
                path = detected
            return self._add_bookmark(name, path)
        elif tool_name == "terminal_remove_bookmark":
            return self._remove_bookmark(kwargs.get("name", ""))
        elif tool_name == "terminal_list_bookmarks":
            return await self._show_bookmarks()
        elif tool_name == "terminal_run":
            return await self._run_command(kwargs.get("command", ""))
        return TaskResult(result=None, guide=f"Unknown context tool: {tool_name}")

    async def _go_to(self, name: str) -> TaskResult:
        self._load_bookmarks()  # refresh in case edited externally
        path = self._bookmarks.get(name.lower().strip())
        if not path:
            # No exact match — show the multi-choice popup instead
            return await self._show_bookmarks()
        await self._type_and_enter(f'cd "{path}"')
        logger.info(f"[Terminal] go_to: {name} → {path}")
        return TaskResult(result=f"Navigated to {path}", guide=f"Navigated to {name}.")

    def _add_bookmark(self, name: str, path: str) -> TaskResult:
        name = name.lower().strip()
        path = path.strip()
        if not name or not path:
            return TaskResult(result="Name and path required.")
        self._bookmarks[name] = path
        self._save_bookmarks()
        logger.info(f"[Terminal] Bookmark saved: {name} → {path}")
        return TaskResult(result=f"Bookmark '{name}' saved.", guide=f"Saved {name}.")

    def _remove_bookmark(self, name: str) -> TaskResult:
        name = name.lower().strip()
        if name not in self._bookmarks:
            return TaskResult(result=f"Bookmark '{name}' not found.")
        del self._bookmarks[name]
        self._save_bookmarks()
        logger.info(f"[Terminal] Bookmark removed: {name}")
        return TaskResult(result=f"Bookmark '{name}' removed.", guide=f"Removed {name}.")

    async def _run_command(self, command: str) -> TaskResult:
        if not command.strip():
            return TaskResult(result="Empty command.")
        await self._type_and_enter(command)
        logger.info(f"[Terminal] Run: {command}")
        return TaskResult(result=f"Ran: {command}")

    async def _type_and_enter(self, text: str):
        """Type text into the terminal via clipboard paste with trailing newline."""
        from glarvis.system.windows import paste_text
        paste_text(text + "\n")

    # ── Context info ──────────────────────────────────────────────────────

    def get_context_info(self) -> str | None:
        self._load_bookmarks()
        bookmark_list = ", ".join(self._bookmarks.keys()) if self._bookmarks else "none"
        cwd = self._get_current_directory() or "unknown"
        return (
            f"Terminal is focused (cwd: {cwd}). "
            f"Voice commands: 'left'/'right' (switch tabs), "
            f"'bookmark' (save current dir), 'bookmarks' (navigate). "
            f"Saved bookmarks: {bookmark_list}."
        )

    # ── SessionTool protocol ─────────────────────────────────────────────

    @property
    def is_done(self) -> bool:
        return self._done_event.is_set()

    async def on_input(self, **kwargs) -> TaskResult:
        return TaskResult(result=None)

    async def close(self) -> None:
        self._done_event.set()
