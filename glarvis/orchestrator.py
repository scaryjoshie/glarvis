"""Orchestrator — wires GlarvisTools into the Pipecat pipeline.

Responsibilities:
1. Registers tools with the LLM service (schema for LLM, handler for system)
2. Injects Board snapshot into LLM context before each turn
3. Delivers notifications via TTS when tasks complete
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import FunctionCallParams, FunctionCallResultProperties

from glarvis.board import Board, Notification
from glarvis.tool import GlarvisTool, TaskResult

if TYPE_CHECKING:
    from pipecat.pipeline.task import PipelineTask
    from pipecat.services.llm_service import LLMService


class Orchestrator:
    """Connects GlarvisTools, the Board, and the Pipecat pipeline.

    Usage::

        board = Board()
        orchestrator = Orchestrator(board, llm, context, task)

        # Register tools
        orchestrator.register(SearchFiles())
        orchestrator.register(CheckCalendar())

        # Tools are now available to the LLM, results route through the Board
    """

    def __init__(
        self,
        board: Board,
        llm: LLMService,
        context: LLMContext,
        pipeline_task: PipelineTask,
    ):
        self.board = board
        self.llm = llm
        self.context = context
        self.pipeline_task = pipeline_task
        self._tools: dict[str, GlarvisTool] = {}

        # Wire up notification delivery
        self.board.on_notification = self._on_notification

        # Inject board state before each LLM turn by patching context
        self._original_system_message = context.messages[0]["content"] if context.messages else ""

    def register(self, tool: GlarvisTool):
        """Register a tool with both the Board system and the LLM."""
        self._tools[tool.name] = tool

        # Register the Pipecat function schema so the LLM knows about it
        # We use register_function with a handler that routes through the Board
        async def _handler(params: FunctionCallParams):
            result = await self._execute_tool(tool, params)
            # Always pass results back to the LLM context so it remembers them.
            # run_llm controls whether the LLM generates a spoken response about it.
            await params.result_callback(
                result.value if result else None,
            )

        self.llm.register_function(
            tool.name,
            _handler,
            cancel_on_interruption=tool.cancel_on_interruption,
        )

        logger.info(f"[Orchestrator] Registered tool: {tool.name}")

    async def _execute_tool(self, tool: GlarvisTool, params: FunctionCallParams) -> TaskResult:
        """Execute a tool, routing through the Board for lifecycle management."""
        kwargs = dict(params.arguments)

        if tool.ttl or tool.notification != "silent":
            # Async/background tool — spawn on the Board
            task_id = await self.board.spawn(tool, kwargs)
            # Return a placeholder; the Board handles completion
            return TaskResult(
                value=f"Task {task_id} started",
                display_text=f"{tool.name} is running",
            )
        else:
            # Simple synchronous tool — run inline
            try:
                await tool.on_start()
                result = await tool.run(**kwargs)
                await tool.on_complete(result)
                return result
            except Exception as e:
                logger.error(f"[Orchestrator] {tool.name} failed: {e}")
                return TaskResult(value=f"Error: {e}")

    def _on_notification(self, notif: Notification):
        """Deliver a notification to the user via TTS."""
        logger.info(f"[Orchestrator] Notification: {notif.message}")
        # Queue a TTS frame to speak the notification
        frame = TTSSpeakFrame(text=notif.message)
        # Use queue_frame on the pipeline task to inject into the pipeline
        self.pipeline_task.queue_frame(frame)

    def inject_board_context(self):
        """Update the system message with current Board state.

        Call this before each LLM turn to give the agent awareness of
        active/completed tasks. Modifies the first system message in-place.
        """
        snapshot = self.board.snapshot()
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
