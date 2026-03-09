"""Terminal — app-specific context for Windows Terminal.

Auto-activates when Windows Terminal gains focus. Provides:
- Tab switching via left/right voice intercepts (Ctrl+Shift+Tab / Ctrl+Tab)
- Directory bookmarks with native file picker for creation
- "bookmark" opens file picker to save a new bookmark
- "bookmarks" shows multi-choice popup to navigate
"""

from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema

from glarvis.tool import AppSessionTool, Function, Intercept, Keyword, TaskResult


# Virtual key codes
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_TAB = 0x09
VK_0 = 0x30  # VK_1 = 0x31, VK_2 = 0x32, etc.

# Number words for intercepts
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "yes": 1, "no": 2,
}


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
            Keyword("bookmark", self._bookmark_via_picker),
            Keyword("bookmark this", self._bookmark_via_picker),
            Keyword("save bookmark", self._bookmark_via_picker),
            Keyword("bookmarks", self._show_bookmarks),
            Keyword("open bookmark", self._show_bookmarks),
            Keyword("open bookmarks", self._show_bookmarks),
            Keyword("go to", self._show_bookmarks),
            Keyword("cli", self._start_cli),
            Keyword("start cli", self._start_cli),
            Function(self._match_number),
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

    async def _match_number(self, text: str) -> TaskResult | None:
        """Match number words (one-six, yes/no) and send the corresponding key."""
        n = _NUMBER_WORDS.get(text)
        if n is None:
            return None
        from glarvis.system.windows import send_key
        send_key(VK_0 + n)
        logger.info(f"[Terminal] Number shortcut: {text} → {n}")
        return TaskResult(result=f"Pressed {n}.", guide=f"{n}.")

    async def _start_cli(self) -> TaskResult:
        await self._type_and_enter("claude")
        logger.info("[Terminal] Starting Claude Code")
        return TaskResult(result="Started Claude Code.", guide="Started.")

    async def _bookmark_via_picker(self) -> TaskResult:
        """Open a native file picker to select a directory, then save it as a bookmark."""
        path = await self.handle.pick_directory("Select directory to bookmark")
        if not path:
            return TaskResult(result="Cancelled.", guide="Cancelled.")

        # Auto-name from last folder
        parts = path.replace("\\", "/").rstrip("/").split("/")
        name = parts[-1].lower() if parts else "unnamed"

        if name in self._bookmarks and self._bookmarks[name] == path:
            return TaskResult(result=f"Bookmark '{name}' already exists.", guide=f"{name} is already bookmarked.")

        self._bookmarks[name] = path
        self._save_bookmarks()
        logger.info(f"[Terminal] Bookmarked: {name} → {path}")
        return TaskResult(result=f"Bookmarked '{name}' → {path}", guide=f"Bookmarked as {name}.")

    async def _show_bookmarks(self) -> TaskResult:
        """Show a multi-choice popup with all bookmarks + create option."""
        self._load_bookmarks()

        options = []
        for name, path in self._bookmarks.items():
            options.append({
                "text": f"{name}  —  {path}",
                "action": {"tool": "terminal_go_to", "args": {"name": name}},
            })

        # Always show "New bookmark" as the last option
        options.append({
            "text": "+ New bookmark...",
            "action": {"tool": "terminal_new_bookmark"},
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
                name="terminal_new_bookmark",
                description="Open a file picker to create a new directory bookmark.",
                properties={},
                required=[],
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
        elif tool_name == "terminal_new_bookmark":
            return await self._bookmark_via_picker()
        elif tool_name == "terminal_remove_bookmark":
            return self._remove_bookmark(kwargs.get("name", ""))
        elif tool_name == "terminal_list_bookmarks":
            return await self._show_bookmarks()
        elif tool_name == "terminal_run":
            return await self._run_command(kwargs.get("command", ""))
        return TaskResult(result=None, guide=f"Unknown context tool: {tool_name}")

    async def _go_to(self, name: str) -> TaskResult:
        self._load_bookmarks()
        path = self._bookmarks.get(name.lower().strip())
        if not path:
            return await self._show_bookmarks()
        await self._type_and_enter(f'cd "{path}"')
        logger.info(f"[Terminal] go_to: {name} → {path}")
        return TaskResult(result=f"Navigated to {path}", guide=f"Navigated to {name}.")

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
        from glarvis.system.windows import paste_text
        paste_text(text + "\n")

    # ── Context info ──────────────────────────────────────────────────────

    def get_context_info(self) -> str | None:
        self._load_bookmarks()
        bookmark_list = ", ".join(self._bookmarks.keys()) if self._bookmarks else "none"
        return (
            f"Terminal is focused. "
            f"Voice commands: 'left'/'right' (switch tabs), "
            f"'bookmark' (save new via file picker), 'bookmarks' (navigate), "
            f"'cli' (start Claude Code). "
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
