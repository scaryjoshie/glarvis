"""Terminal — app-specific context for Windows Terminal.

Auto-activates when Windows Terminal gains focus. Provides:
- Tab switching via left/right voice intercepts (Ctrl+Shift+Tab / Ctrl+Tab)
- Directory bookmarks (named paths, navigable by voice or LLM tool call)
"""

from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema

from glarvis.tool import AppSessionTool, Intercept, Keyword, TaskResult


# Virtual key codes
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_TAB = 0x09
VK_RETURN = 0x0D


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

    # ── Context intercepts (active only when terminal focused) ────────────

    def get_context_intercepts(self) -> list[Intercept]:
        return [
            Keyword("left", self._tab_left),
            Keyword("right", self._tab_right),
            Keyword("previous tab", self._tab_left),
            Keyword("next tab", self._tab_right),
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
                description="Save a directory bookmark.",
                properties={
                    "name": {"type": "string", "description": "Bookmark name"},
                    "path": {"type": "string", "description": "Directory path"},
                },
                required=["name", "path"],
            ),
            FunctionSchema(
                name="terminal_remove_bookmark",
                description="Remove a directory bookmark.",
                properties={"name": {"type": "string", "description": "Bookmark name"}},
                required=["name"],
            ),
            FunctionSchema(
                name="terminal_list_bookmarks",
                description="List all directory bookmarks.",
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
            return self._add_bookmark(kwargs.get("name", ""), kwargs.get("path", ""))
        elif tool_name == "terminal_remove_bookmark":
            return self._remove_bookmark(kwargs.get("name", ""))
        elif tool_name == "terminal_list_bookmarks":
            return self._list_bookmarks()
        elif tool_name == "terminal_run":
            return await self._run_command(kwargs.get("command", ""))
        return TaskResult(result=None, guide=f"Unknown context tool: {tool_name}")

    async def _go_to(self, name: str) -> TaskResult:
        self._load_bookmarks()  # refresh in case edited externally
        path = self._bookmarks.get(name.lower().strip())
        if not path:
            available = ", ".join(self._bookmarks.keys()) or "none"
            return TaskResult(
                result=f"Bookmark '{name}' not found. Available: {available}",
                guide=f"No bookmark called {name}.",
            )
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

    def _list_bookmarks(self) -> TaskResult:
        self._load_bookmarks()
        if not self._bookmarks:
            return TaskResult(result="No bookmarks saved.", guide="No bookmarks yet.")
        lines = [f"- **{name}**: `{path}`" for name, path in self._bookmarks.items()]
        return TaskResult(
            result=self._bookmarks,
            board_content="## Directory Bookmarks\n" + "\n".join(lines),
        )

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
        return (
            f"Terminal is focused. Say 'left'/'right' to switch tabs. "
            f"Bookmarks: {bookmark_list}."
        )

    # ── SessionTool protocol ─────────────────────────────────────────────

    @property
    def is_done(self) -> bool:
        return self._done_event.is_set()

    async def on_input(self, **kwargs) -> TaskResult:
        return TaskResult(result=None)

    async def close(self) -> None:
        self._done_event.set()
