"""Orchestrator — wires Tools into the Pipecat pipeline.

Responsibilities:
1. Registers tools with the LLM service (schema for LLM, handler for system)
2. Injects task state into LLM context before each turn
3. Delivers notifications via TTS when tasks complete
4. Manages session context (dynamic tool injection for active sessions)
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import FunctionCallParams

from glarvis.task_manager import TaskManager, Notification, TaskState
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
        self._board_post_index = 0

        # Session context tracking
        # task_id → TaskState for sessions with active context
        self._active_contexts: dict[str, TaskState] = {}
        # context tool name → task_id (for routing context tool calls)
        self._context_tool_map: dict[str, str] = {}

        # Wire up notification delivery
        self.task_manager.on_notification = self._on_notification
        self.task_manager.on_change = self._on_task_change
        self.task_manager.on_board_post = self._on_board_post
        self.task_manager.on_finalize = self._on_task_finalize

        # Inject task state before each LLM turn by patching context
        self._original_system_message = context.messages[0]["content"] if context.messages else ""

    def set_broadcast(self, broadcast_fn: Callable[[dict], Coroutine]):
        """Set the broadcast function for sending UI updates."""
        self._broadcast = broadcast_fn

    def _next_transcript_id(self) -> int:
        self._transcript_id += 1
        return self._transcript_id

    async def broadcast_board_post(self, author: str, content: str) -> int:
        """Send a board post to the UI. Returns the post index."""
        index = self._board_post_index
        self._board_post_index += 1
        if not self._broadcast:
            return index
        await self._broadcast({
            "type": "board_post",
            "author": author,
            "content": content,
            "timestamp": time.time(),
        })
        return index

    async def broadcast_welcome(self):
        """Post available tools to the board on connection."""
        if not self._tools:
            return

        lines = ["# Minerva\n"]
        for tool in self._tools.values():
            tool_type = type(tool).__bases__[0].__name__
            tag = {"InlineTool": "instant", "AsyncTool": "background", "SessionTool": "session"}.get(tool_type, tool_type)
            lines.append(f"### {tool.name}")
            lines.append(f"`{tag}` {tool.description}\n")

        lines.append("---")
        lines.append("*Say or type anything to get started.*")

        await self.broadcast_board_post("minerva", "\n".join(lines))

    async def broadcast_transcript(
        self, role: str, text: str, entry_type: str = "speech",
        tool: str | None = None, tool_args: dict | None = None,
        tool_result: Any = None,
    ):
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
        if tool_args is not None:
            entry["tool_args"] = tool_args
        if tool_result is not None:
            entry["tool_result"] = str(tool_result)[:500]
        await self._broadcast({"type": "transcript_add", "entry": entry})

    # ── Tool registration ────────────────────────────────────────────────────

    def register(self, tool: BaseTool):
        """Register a tool with both the TaskManager and the LLM."""
        self._tools[tool.name] = tool
        self._register_handler(tool.name)
        logger.info(f"[Orchestrator] Registered tool: {tool.name}")

    def _register_handler(self, tool_name: str):
        """Register a Pipecat function handler for a tool name."""
        async def _handler(params: FunctionCallParams):
            result = await self._execute_tool(tool_name, params)
            await params.result_callback(
                result.result if result else None,
            )

        tool = self._tools.get(tool_name)
        cancel = tool.cancel_on_interruption if tool else True
        self.llm.register_function(tool_name, _handler, cancel_on_interruption=cancel)

    # ── Session context management ───────────────────────────────────────────

    def _find_session_state(self, task_id: str) -> TaskState | None:
        """Find a TaskState by ID in active tasks or recent history."""
        state = self.task_manager.active.get(task_id)
        if state:
            return state
        for s in self.task_manager.history:
            if s.id == task_id:
                return s
        return None

    def _find_active_session_for_tool(self, tool_name: str) -> TaskState | None:
        """Find an active (running) session for a given tool name."""
        for state in self.task_manager.active.values():
            if isinstance(state.tool, SessionTool) and state.tool.name == tool_name:
                return state
        return None

    def enter_context(self, task_id: str) -> bool:
        """Activate a session's context. Returns True if successful."""
        state = self._find_session_state(task_id)
        if not state or not isinstance(state.tool, SessionTool):
            logger.warning(f"[Orchestrator] Cannot enter context: {task_id} is not a session")
            return False

        if task_id in self._active_contexts:
            logger.debug(f"[Orchestrator] Context already active for {task_id}")
            return True

        self._active_contexts[task_id] = state
        self._rebuild_tools()
        self._on_task_change()  # update UI with context_active flag
        logger.info(f"[Orchestrator] Entered context for {task_id} ({state.tool.name})")
        return True

    def exit_context(self, task_id: str) -> bool:
        """Deactivate a session's context. Returns True if it was active."""
        if task_id not in self._active_contexts:
            return False

        state = self._active_contexts.pop(task_id)
        self._rebuild_tools()
        self._on_task_change()
        logger.info(f"[Orchestrator] Exited context for {task_id} ({state.tool.name})")
        return True

    def toggle_context(self, task_id: str) -> bool:
        """Toggle a session's context. Returns True if context is now active."""
        if task_id in self._active_contexts:
            self.exit_context(task_id)
            return False
        else:
            return self.enter_context(task_id)

    def _rebuild_tools(self):
        """Rebuild LLMContext.tools with base tools + active context tools.
        Pipecat reads context.tools fresh each turn, so no pipeline rebuild needed."""
        # Base tool schemas
        schemas = [tool.to_function_schema() for tool in self._tools.values()]

        # Collect context tools from active sessions and build routing map
        self._context_tool_map.clear()
        for task_id, state in self._active_contexts.items():
            session: SessionTool = state.tool
            for ctx_schema in session.get_context_tools():
                schemas.append(ctx_schema)
                self._context_tool_map[ctx_schema.name] = task_id
                # Register a handler for this context tool if not already registered
                if not self.llm.has_function(ctx_schema.name):
                    self._register_context_handler(ctx_schema.name)

        if schemas:
            self.context.tools = ToolsSchema(standard_tools=schemas)
        else:
            self.context.tools = None

        logger.debug(f"[Orchestrator] Rebuilt tools: {len(schemas)} total, "
                     f"{len(self._context_tool_map)} context tools")

    def _register_context_handler(self, tool_name: str):
        """Register a Pipecat function handler for a context tool."""
        async def _handler(params: FunctionCallParams):
            result = await self._execute_tool(tool_name, params)
            await params.result_callback(
                result.result if result else None,
            )

        self.llm.register_function(tool_name, _handler, cancel_on_interruption=True)

    # ── Tool execution ───────────────────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, params: FunctionCallParams) -> TaskResult:
        """Execute a tool, routing by type and context."""
        kwargs = dict(params.arguments)

        # Broadcast tool call to transcript
        await self.broadcast_transcript(
            "assistant", tool_name,
            entry_type="tool_call", tool=tool_name,
            tool_args=kwargs,
        )

        # 1. Check if this is a context tool call
        if tool_name in self._context_tool_map:
            task_id = self._context_tool_map[tool_name]
            state = self._active_contexts.get(task_id)
            if state and isinstance(state.tool, SessionTool):
                try:
                    result = await state.tool.handle_context_call(tool_name, **kwargs)
                except Exception as e:
                    logger.error(f"[Orchestrator] Context tool {tool_name} failed: {e}")
                    result = TaskResult(result=f"Error: {e}")

                if result and result.board_content:
                    await self.broadcast_board_post(state.tool.name, result.board_content)

                await self.broadcast_transcript(
                    "assistant", tool_name,
                    entry_type="tool_result", tool=tool_name,
                    tool_result=result.result if result else None,
                )
                return result

        # 2. Look up the registered tool
        tool = self._tools.get(tool_name)
        if not tool:
            logger.error(f"[Orchestrator] Unknown tool: {tool_name}")
            result = TaskResult(result=f"Error: unknown tool {tool_name}")
            await self.broadcast_transcript(
                "assistant", tool_name,
                entry_type="tool_result", tool=tool_name,
                tool_result=result.result,
            )
            return result

        # 3. SessionTool: check for active session → route to on_input()
        if isinstance(tool, SessionTool):
            active_state = self._find_active_session_for_tool(tool_name)
            if active_state:
                # Session already running — route to on_input()
                try:
                    result = await active_state.tool.on_input(**kwargs)
                except Exception as e:
                    logger.error(f"[Orchestrator] {tool.name}.on_input() failed: {e}")
                    result = TaskResult(result=f"Error: {e}")

                if result and result.board_content:
                    await self.broadcast_board_post(tool.name, result.board_content)

                await self.broadcast_transcript(
                    "assistant", tool_name,
                    entry_type="tool_result", tool=tool_name,
                    tool_result=result.result if result else None,
                )
                return result

            # New session — spawn it
            task_id = await self.task_manager.spawn(tool, kwargs)

            # Auto-enter context if the session wants it
            if tool.auto_enter_context:
                self.enter_context(task_id)

            result = TaskResult(
                result=f"Session {task_id} started",
                guide=f"{tool.name} session is running",
            )

        elif isinstance(tool, AsyncTool):
            task_id = await self.task_manager.spawn(tool, kwargs)
            result = TaskResult(
                result=f"Task {task_id} started",
                guide=f"{tool.name} is running",
            )
        else:
            # InlineTool — run directly
            try:
                result = await tool.run(**kwargs)
                if result and result.board_content:
                    await self.broadcast_board_post(tool.name, result.board_content)
            except Exception as e:
                logger.error(f"[Orchestrator] {tool.name} failed: {e}")
                result = TaskResult(result=f"Error: {e}")

        # Broadcast tool result
        await self.broadcast_transcript(
            "assistant", tool_name,
            entry_type="tool_result", tool=tool_name,
            tool_result=result.result if result else None,
        )

        return result

    # ── Notification / broadcast callbacks ───────────────────────────────────

    def _on_notification(self, notif: Notification):
        """Deliver a notification to the user via TTS."""
        logger.info(f"[Orchestrator] Notification: {notif.message}")
        frame = TTSSpeakFrame(text=notif.message)
        self.pipeline_task.queue_frame(frame)

    def _on_task_finalize(self, task_id: str):
        """Called when a task is finalized. Clean up context if it was a session."""
        if task_id in self._active_contexts:
            self.exit_context(task_id)

    def _on_board_post(self, task_id: str, author: str, content: str):
        """Called when an async task posts to the board."""
        if self._broadcast:
            async def _post():
                index = await self.broadcast_board_post(author, content)
                state = self.task_manager.active.get(task_id) or next(
                    (s for s in self.task_manager.history if s.id == task_id), None
                )
                if state:
                    state.board_post_index = index
                    self.task_manager._notify_change()
            asyncio.create_task(_post())

    def _on_task_change(self):
        """Called when any task state changes. Broadcasts to UI."""
        if not self._broadcast:
            return
        tasks = self.task_manager.to_ui_list()
        # Augment with context info
        active_context_ids = set(self._active_contexts.keys())
        for t in tasks:
            state = self._find_session_state(t["id"])
            t["is_session"] = isinstance(state.tool, SessionTool) if state else False
            t["context_active"] = t["id"] in active_context_ids
        asyncio.create_task(self._broadcast({"type": "task_update", "tasks": tasks}))

    # ── Context injection ────────────────────────────────────────────────────

    def inject_task_context(self):
        """Update the system message with current task state.

        Call this before each LLM turn to give the agent awareness of
        active/completed tasks. Modifies the first system message in-place.
        """
        snapshot = self.task_manager.snapshot()

        # Add active context info
        context_lines = []
        for task_id, state in self._active_contexts.items():
            context_lines.append(f"  Active context: {state.tool.name} (session {task_id})")

        if context_lines:
            context_section = "[Active Session Contexts]\n" + "\n".join(context_lines)
            if snapshot:
                snapshot = snapshot + "\n\n" + context_section
            else:
                snapshot = context_section

        if snapshot:
            updated = f"{self._original_system_message}\n\n{snapshot}"
        else:
            updated = self._original_system_message

        if self.context.messages:
            self.context.messages[0]["content"] = updated

    def get_tools_schema(self):
        """Get a ToolsSchema containing all registered tools, for passing to LLMContext."""
        schemas = [tool.to_function_schema() for tool in self._tools.values()]
        if schemas:
            return ToolsSchema(standard_tools=schemas)
        return None
