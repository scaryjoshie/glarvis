"""Tool classes. Tools are self-describing: they declare both their LLM-facing
schema (name, description, parameters) and their system-facing behavior
(notification level, display routing, hooks).

Three tool types:
- InlineTool: runs inline, blocks the LLM turn, returns result directly.
- AsyncTool: spawns on the TaskManager, completes in background.
- SessionTool: long-lived, accepts subsequent input via on_input().

BaseTool is abstract — you must subclass one of the three concrete types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

from pipecat.adapters.schemas.function_schema import FunctionSchema


NotificationLevel = Literal["silent", "notify", "interrupt"]
DisplayMode = Literal["board", "speak", "both", "none"]


@dataclass
class TaskResult:
    """What a tool returns after execution."""

    result: Any = None  # raw data for LLM context
    guide: str | None = None  # natural language hint for the LLM
    board_content: str | None = None  # rich markdown for Board stream
    notify: bool = False  # show as popup when main app not focused


class ToolHandle:
    """Scoped API for tool-to-system communication. Set by orchestrator at registration.

    Decouples tools from orchestrator internals. Tools use self.handle.post_to_board()
    instead of reaching into the orchestrator.
    """

    async def post_to_board(self, content: str, author: str | None = None) -> int:
        """Post markdown to the board. Returns post index."""
        raise NotImplementedError

    async def open_popup(self, popup_type: str, data: dict) -> None:
        """Tell frontend to open a popup window."""
        raise NotImplementedError

    async def close_popup(self) -> None:
        """Tell frontend to close this tool's popup."""
        raise NotImplementedError

    async def close_named_popup(self, name: str) -> None:
        """Tell frontend to close a popup by name."""
        raise NotImplementedError

    async def execute_tool(self, tool_name: str, **kwargs) -> TaskResult:
        """Programmatically execute another tool as if the LLM called it."""
        raise NotImplementedError

class BaseTool(ABC):
    """Abstract base for all tools. Do not subclass directly —
    use InlineTool, AsyncTool, or SessionTool."""

    # ── LLM-facing (tool schema) ──────────────────────────────────────────
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    required: list[str] = []

    # ── System-facing (presentation) ──────────────────────────────────────
    notification: NotificationLevel = "silent"
    display: DisplayMode = "none"
    cancel_on_interruption: bool = True
    shortcuts: list[str] = []  # voice keywords that trigger this tool directly (bypass LLM)

    # ── Set by orchestrator at registration ─────────────────────────────
    handle: ToolHandle | None = None

    # ── Core execution ────────────────────────────────────────────────────

    @abstractmethod
    async def run(self, **kwargs) -> TaskResult:
        """Execute the tool. Override this in subclasses."""
        ...

    # ── Pipecat integration ───────────────────────────────────────────────

    def to_function_schema(self) -> FunctionSchema:
        """Convert to Pipecat's FunctionSchema for LLM tool registration."""
        return FunctionSchema(
            name=self.name,
            description=self.description,
            properties=self.parameters,
            required=self.required,
        )


class InlineTool(BaseTool):
    """Runs directly in the LLM turn, returns result immediately.

    Does not appear in TaskDisplay. Use for fast, synchronous operations.

    Example::

        class GetTime(InlineTool):
            name = "get_time"
            description = "Get the current time."

            async def run(self) -> TaskResult:
                now = datetime.now().strftime("%I:%M %p")
                return TaskResult(result=now, guide=f"It's {now}")
    """

    notification: NotificationLevel = "silent"
    display: DisplayMode = "none"


class AsyncTool(BaseTool):
    """Spawns on the TaskManager, completes asynchronously.

    Shows in TaskDisplay. Results delivered via notification and/or Board stream.
    Use for operations that take time or that the user might want to monitor.

    Example::

        class SearchFiles(AsyncTool):
            name = "search_files"
            description = "Search the codebase by pattern."
            parameters = {"pattern": {"type": "string", "description": "Search pattern"}}
            required = ["pattern"]

            async def run(self, pattern: str = "", **kwargs) -> TaskResult:
                matches = glob.glob(f"**/*{pattern}*", recursive=True)
                return TaskResult(
                    result=matches,
                    guide=f"Found {len(matches)} files matching {pattern}",
                    board_content="\\n".join(matches[:20]),
                )
    """

    notification: NotificationLevel = "notify"
    display: DisplayMode = "board"
    ttl: int | None = None
    persist_in_display: bool = False  # auto-hide from TaskDisplay on completion

    async def on_start(self) -> None:
        """Called when the task begins executing."""
        pass

    async def on_progress(self, update: str) -> None:
        """Called by the task itself to report progress."""
        pass

    async def on_complete(self, result: TaskResult) -> None:
        """Called after run() finishes successfully."""
        pass

    async def on_expire(self) -> None:
        """Called if the task exceeds its TTL."""
        pass

    def task_display_status(self, elapsed: float) -> str:
        """Status text for TaskDisplay. Override for custom display."""
        return f"{self.name} ({elapsed:.1f}s)"


class SessionTool(AsyncTool):
    """Long-lived interactive tool. Stays alive after initial run(),
    accepts subsequent input via on_input(), until explicitly closed.

    Shows in TaskDisplay as a persistent entry. Use for interactive sessions
    like Claude Code, browser automation, or anything that maintains state
    across multiple interactions.

    Session context: when a session's context is active, its context tools
    are injected into the LLM prompt. Override get_context_tools() and
    handle_context_call() to provide temporary capabilities.

    Example::

        class ClaudeCode(SessionTool):
            name = "claude_code"
            description = "Interactive Claude Code session."

            async def run(self, prompt: str = "", **kwargs) -> TaskResult:
                self.session = start_session()
                result = await self.session.send(prompt)
                return TaskResult(result=result, guide="Session started")

            async def on_input(self, message: str = "", **kwargs) -> TaskResult:
                result = await self.session.send(message)
                return TaskResult(result=result)

            async def close(self) -> None:
                await self.session.stop()
    """

    ttl: int | None = None
    persist_in_display: bool = True  # session tools stay visible by default
    auto_enter_context: bool = True  # enter context automatically on run()

    @abstractmethod
    async def on_input(self, **kwargs) -> TaskResult:
        """Handle subsequent input to an active session."""
        ...

    def get_context_tools(self) -> list[FunctionSchema]:
        """Tools available while this session's context is active.
        Override to inject temporary tools. Can vary based on state."""
        return []

    async def handle_context_call(self, tool_name: str, **kwargs) -> TaskResult:
        """Handle a call to one of this session's context tools."""
        return TaskResult(result=None, guide=f"Unknown context tool: {tool_name}")

    @property
    def is_done(self) -> bool:
        """Whether the session has resolved. Checked after intercept to auto-exit context."""
        return False

    async def intercept(self, text: str) -> TaskResult | None:
        """Try to claim a user input before the LLM sees it.

        Return a TaskResult to consume the input, or None to let it through.
        Override in subclasses that want to handle direct voice input
        (e.g., number words for multi-choice). Must be fast — runs on
        every transcription frame while the session context is active.
        """
        return None

    async def close(self) -> None:
        """Clean up the session. Called when the task is cancelled or dismissed."""
        pass
