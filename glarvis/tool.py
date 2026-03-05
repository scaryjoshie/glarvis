"""Base tool class. Tools are self-describing: they declare both their LLM-facing
schema (name, description, parameters) and their system-facing behavior
(notification level, display routing, hooks)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Literal

from pipecat.adapters.schemas.function_schema import FunctionSchema


NotificationLevel = Literal["silent", "notify", "interrupt"]
DisplayMode = Literal["board", "speak", "both", "none"]


@dataclass
class TaskResult:
    """What a tool returns after execution."""

    value: Any = None
    display_text: str | None = None  # what to show on board/terminal
    speak_text: str | None = None  # what to say (only used if display includes "speak")


class Tool:
    """Base class for all tools.

    Subclass this to create a tool. The LLM sees `name`, `description`, and
    `parameters`. The system uses `notification`, `display`, `ttl`, and hooks
    to decide what to do with results — the LLM never sees these.

    Example::

        class SearchFiles(Tool):
            name = "search_files"
            description = "Search the codebase. Results display on the board."
            parameters = {
                "query": {"type": "string", "description": "Search query"}
            }
            required = ["query"]

            notification = "notify"
            display = "board"

            async def run(self, query: str) -> TaskResult:
                results = do_search(query)
                return TaskResult(
                    value=results,
                    display_text=f"Found {len(results)} matches",
                )
    """

    # ── LLM-facing (tool schema) ──────────────────────────────────────────
    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    required: list[str] = []

    # ── System-facing (behavior) ──────────────────────────────────────────
    notification: NotificationLevel = "notify"
    display: DisplayMode = "board"
    ttl: int | None = None  # seconds, None = no expiry
    cancel_on_interruption: bool = True

    # ── Lifecycle hooks (override in subclass if needed) ──────────────────

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

    # ── Core execution ────────────────────────────────────────────────────

    async def run(self, **kwargs) -> TaskResult:
        """Execute the tool. Override this in subclasses."""
        raise NotImplementedError

    # ── Pipecat integration ───────────────────────────────────────────────

    def to_function_schema(self) -> FunctionSchema:
        """Convert to Pipecat's FunctionSchema for LLM tool registration."""
        return FunctionSchema(
            name=self.name,
            description=self.description,
            properties=self.parameters,
            required=self.required,
        )

    def board_status(self, elapsed: float) -> str:
        """Default board status line. Override for custom display."""
        return f"{self.name} (running, {elapsed:.1f}s)"
