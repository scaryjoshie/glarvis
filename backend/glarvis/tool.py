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
from typing import Any, Callable, Literal, TYPE_CHECKING

from pipecat.adapters.schemas.function_schema import FunctionSchema

if TYPE_CHECKING:
    from glarvis.handle import ToolHandle
    from glarvis.system.monitor import SystemMonitor, WindowInfo


NotificationLevel = Literal["silent", "notify", "interrupt"]
DisplayMode = Literal["board", "speak", "both", "none"]


@dataclass
class TaskResult:
    """What a tool returns after execution."""

    result: Any = None  # raw data for LLM context
    guide: str | None = None  # natural language hint for the LLM
    board_content: str | None = None  # rich markdown for Board stream
    notify: bool = False  # show as popup when main app not focused


# ── Intercept types ──────────────────────────────────────────────────────

@dataclass
class Keyword:
    """Exact keyword match → handler() with no args."""
    word: str
    handler: Callable  # async () -> TaskResult | None

@dataclass
class Function:
    """Custom matcher → handler(cleaned_text)."""
    handler: Callable  # async (text: str) -> TaskResult | None

Intercept = Keyword | Function


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

    # ── Set by orchestrator at registration ─────────────────────────────
    handle: ToolHandle | None = None

    @property
    def system(self) -> SystemMonitor | None:
        return self.handle.system if self.handle else None

    # ── Core execution ────────────────────────────────────────────────────

    @abstractmethod
    async def run(self, **kwargs) -> TaskResult:
        """Execute the tool. Override this in subclasses."""
        ...

    # ── Intercepts ────────────────────────────────────────────────────────

    def get_intercepts(self) -> list[Intercept]:
        """Global intercepts. Called once at orchestrator.register() time. Always active."""
        return []

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
    monitors_speech: bool = False  # when True, on_speech(text) is called for every STT frame
    hides_speech: bool = False  # when True (and monitors_speech), speech doesn't reach the LLM

    @abstractmethod
    async def on_input(self, **kwargs) -> TaskResult:
        """Handle subsequent input to an active session."""
        ...

    async def on_speech(self, text: str) -> None:
        """Receive raw STT text when captures_speech is True.
        Called for every transcription frame while this session's context is active."""
        pass

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

    def get_context_info(self) -> str | None:
        """Extra context injected into the system message while this session is active.
        Called every turn by prepare_for_turn(). Return None to add nothing."""
        return None

    def get_context_intercepts(self) -> list[Intercept]:
        """Context intercepts. Called at enter_context(), removed at exit_context().
        Override to register keywords/functions active only while this session's context is active."""
        return []

    async def close(self) -> None:
        """Clean up the session. Called when the task is cancelled or dismissed."""
        pass


class AppSessionTool(SessionTool):
    """Session bound to a specific app window. Mutually exclusive with other AppSessionTools.

    When the matched window gains focus, the orchestrator auto-enters this session's context
    (and exits any other AppSessionTool's context). Context tools can vary based on focus state.

    Subclass and override matches_window() to define which windows belong to this tool.
    """

    auto_enter_context: bool = False  # orchestrator manages context via focus, not on spawn
    app_name: str = ""  # process name to match (e.g. "code", "windowsterminal")

    def matches_window(self, window: WindowInfo) -> bool:
        """Does this window belong to this tool's app?
        Default: matches on app_name. Override for custom logic."""
        return bool(self.app_name) and window.app == self.app_name

    @property
    def is_focused(self) -> bool:
        """Is this tool's app currently in the foreground?"""
        if not self.system:
            return False
        fg = self.system.state.foreground_id
        if fg is None:
            return False
        win = next((w for w in self.system.state.windows if w.id == fg), None)
        return win is not None and self.matches_window(win)
