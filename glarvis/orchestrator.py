"""Orchestrator — wires Tools into the Pipecat pipeline.

Responsibilities:
1. Registers tools with the LLM service (schema for LLM, handler for system)
2. Injects task state into LLM context before each turn
3. Delivers notifications via TTS when tasks complete
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import FunctionCallParams, FunctionCallResultProperties

from glarvis.task_manager import TaskManager, Notification
from glarvis.tool import Tool, TaskResult

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
        self._tools: dict[str, Tool] = {}

        # Wire up notification delivery
        self.task_manager.on_notification = self._on_notification

        # Inject task state before each LLM turn by patching context
        self._original_system_message = context.messages[0]["content"] if context.messages else ""

    def register(self, tool: Tool):
        """Register a tool with both the TaskManager and the LLM."""
        self._tools[tool.name] = tool

        # Register the Pipecat function schema so the LLM knows about it
        # We use register_function with a handler that routes through the TaskManager
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

    async def _execute_tool(self, tool: Tool, params: FunctionCallParams) -> TaskResult:
        """Execute a tool, routing through the TaskManager for lifecycle management."""
        kwargs = dict(params.arguments)

        if tool.ttl or tool.notification != "silent":
            # Async/background tool — spawn on the TaskManager
            task_id = await self.task_manager.spawn(tool, kwargs)
            # Return a placeholder; the TaskManager handles completion
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
