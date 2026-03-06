"""Orchestrator — wires Tools into the Pipecat pipeline.

Responsibilities:
1. Registers tools with the LLM service (schema for LLM, handler for system)
2. Injects task state into LLM context before each turn
3. Delivers notifications via TTS when tasks complete
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import FunctionCallParams, FunctionCallResultProperties

from glarvis.task_manager import TaskManager, Notification
from glarvis.tool import AsyncTool, BaseTool, SessionTool, TaskResult

if TYPE_CHECKING:
    from pipecat.pipeline.task import PipelineTask
    from pipecat.services.llm_service import LLMService


class Orchestrator:
    """Connects Tools, the TaskManager, and the Pipecat pipeline.

    Usage::

        task_manager = TaskManager()
        orchestrator = Orchestrator(task_manager, llm, context, task)

        # Register tools
        orchestrator.register(SearchFiles())
        orchestrator.register(CheckCalendar())

        # Tools are now available to the LLM, results route through the TaskManager
    """

    def __init__(
        self,
        task_manager: TaskManager,
        llm: LLMService,
        context: LLMContext,
        pipeline_task: PipelineTask,
    ):
        self.task_manager = task_manager
        self.llm = llm
        self.context = context
        self.pipeline_task = pipeline_task
        self._tools: dict[str, BaseTool] = {}
        self._broadcast: Callable[[dict], Coroutine] | None = None
        self._transcript_id = 0

        # Wire up notification delivery
        self.task_manager.on_notification = self._on_notification
        self.task_manager.on_change = self._on_task_change
        self.task_manager.on_board_post = self._on_board_post

        # Inject task state before each LLM turn by patching context
        self._original_system_message = context.messages[0]["content"] if context.messages else ""

    def set_broadcast(self, broadcast_fn: Callable[[dict], Coroutine]):
        """Set the broadcast function for sending UI updates."""
        self._broadcast = broadcast_fn

    def _next_transcript_id(self) -> int:
        self._transcript_id += 1
        return self._transcript_id

    async def broadcast_board_post(self, author: str, content: str):
        """Send a board post to the UI."""
        if not self._broadcast:
            return
        await self._broadcast({
            "type": "board_post",
            "author": author,
            "content": content,
            "timestamp": time.time(),
        })

    async def broadcast_transcript(self, role: str, text: str, entry_type: str = "speech", tool: str | None = None):
        """Send a transcript entry to the UI."""
        if not self._broadcast:
            return
        entry = {
            "id": self._next_transcript_id(),
            "role": role,
            "text": text,
            "type": entry_type,
        }
        if tool:
            entry["tool"] = tool
        await self._broadcast({"type": "transcript_add", "entry": entry})

    def register(self, tool: BaseTool):
        """Register a tool with both the TaskManager and the LLM."""
        self._tools[tool.name] = tool

        # Register the Pipecat function schema so the LLM knows about it
        # We use register_function with a handler that routes through the TaskManager
        async def _handler(params: FunctionCallParams):
            result = await self._execute_tool(tool, params)
            # Always pass results back to the LLM context so it remembers them.
            # run_llm controls whether the LLM generates a spoken response about it.
            await params.result_callback(
                result.result if result else None,
            )

        self.llm.register_function(
            tool.name,
            _handler,
            cancel_on_interruption=tool.cancel_on_interruption,
        )

        logger.info(f"[Orchestrator] Registered tool: {tool.name}")

    async def _execute_tool(self, tool: BaseTool, params: FunctionCallParams) -> TaskResult:
        """Execute a tool, routing by type: isinstance check, not metadata."""
        kwargs = dict(params.arguments)

        # Broadcast tool call to transcript
        await self.broadcast_transcript("assistant", tool.name, entry_type="tool_call", tool=tool.name)

        if isinstance(tool, SessionTool):
            # TODO: check for active session and route to on_input()
            task_id = await self.task_manager.spawn(tool, kwargs)
            return TaskResult(
                result=f"Task {task_id} started",
                guide=f"{tool.name} session is running",
            )
        elif isinstance(tool, AsyncTool):
            # Background tool — spawn on the TaskManager
            task_id = await self.task_manager.spawn(tool, kwargs)
            return TaskResult(
                result=f"Task {task_id} started",
                guide=f"{tool.name} is running",
            )
        else:
            # InlineTool — run directly, return result
            try:
                result = await tool.run(**kwargs)
                if result and result.board_content:
                    await self.broadcast_board_post(tool.name, result.board_content)
                return result
            except Exception as e:
                logger.error(f"[Orchestrator] {tool.name} failed: {e}")
                return TaskResult(result=f"Error: {e}")

    def _on_notification(self, notif: Notification):
        """Deliver a notification to the user via TTS."""
        logger.info(f"[Orchestrator] Notification: {notif.message}")
        # Queue a TTS frame to speak the notification
        frame = TTSSpeakFrame(text=notif.message)
        # Use queue_frame on the pipeline task to inject into the pipeline
        self.pipeline_task.queue_frame(frame)

    def _on_board_post(self, author: str, content: str):
        """Called when an async task posts to the board."""
        if self._broadcast:
            asyncio.create_task(self.broadcast_board_post(author, content))

    def _on_task_change(self):
        """Called when any task state changes. Broadcasts to UI."""
        if not self._broadcast:
            return
        tasks = self.task_manager.to_ui_list()
        asyncio.create_task(self._broadcast({"type": "task_update", "tasks": tasks}))

    def inject_task_context(self):
        """Update the system message with current task state.

        Call this before each LLM turn to give the agent awareness of
        active/completed tasks. Modifies the first system message in-place.
        """
        snapshot = self.task_manager.snapshot()
        if snapshot:
            updated = f"{self._original_system_message}\n\n{snapshot}"
        else:
            updated = self._original_system_message

        if self.context.messages:
            self.context.messages[0]["content"] = updated

    def get_tools_schema(self):
        """Get a ToolsSchema containing all registered tools, for passing to LLMContext."""
        from pipecat.adapters.schemas.tools_schema import ToolsSchema

        schemas = [tool.to_function_schema() for tool in self._tools.values()]
        if schemas:
            return ToolsSchema(standard_tools=schemas)
        return None
