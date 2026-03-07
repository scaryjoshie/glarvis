"""Orchestrator — wires Tools into the Pipecat pipeline.

Registers tools, routes tool calls, manages session context,
and prepares LLM context before each turn.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TranscriptionFrame, TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.llm_service import FunctionCallParams

from glarvis.prompt import build_system_message
from glarvis.task_manager import TaskManager, Notification, TaskState
from glarvis.tool import AsyncTool, BaseTool, SessionTool, TaskResult, ToolHandle

if TYPE_CHECKING:
    from pipecat.pipeline.task import PipelineTask
    from pipecat.services.llm_service import LLMService
    from glarvis.system.monitor import SystemMonitor


class _OrchestratorToolHandle(ToolHandle):
    """Concrete ToolHandle backed by the orchestrator."""

    def __init__(self, orch: Orchestrator, tool_name: str):
        self._orch = orch
        self._name = tool_name

    async def post_to_board(self, content: str, author: str | None = None) -> int:
        return await self._orch.broadcast_board_post(author or self._name, content)

    async def open_popup(self, popup_type: str, data: dict) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_open", "popup_type": popup_type,
            "tool_name": self._name, "data": data,
        })

    async def close_popup(self) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_close", "tool_name": self._name,
        })

    async def close_named_popup(self, name: str) -> None:
        await self._orch._broadcast_msg({
            "type": "popup_close", "tool_name": name,
        })


class Orchestrator:
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
        self.system_monitor: SystemMonitor | None = None
        self._transcript_id = 0
        self._board_post_index = 0

        self._active_contexts: dict[str, TaskState] = {}  # task_id → TaskState
        self._context_tool_map: dict[str, str] = {}  # context tool name → task_id

        self.task_manager.on_notification = self._on_notification
        self.task_manager.on_change = self._on_task_change
        self.task_manager.on_board_post = self._on_board_post
        self.task_manager.on_finalize = self._on_task_finalize

        self._original_system_message = context.messages[0]["content"] if context.messages else ""

    # ── Broadcasting ─────────────────────────────────────────────────────────

    def set_broadcast(self, broadcast_fn: Callable[[dict], Coroutine]):
        self._broadcast = broadcast_fn

    async def _broadcast_msg(self, msg: dict):
        if self._broadcast:
            await self._broadcast(msg)

    async def broadcast_board_post(self, author: str, content: str, notify: bool = False) -> int:
        index = self._board_post_index
        self._board_post_index += 1
        await self._broadcast_msg({
            "type": "board_post", "author": author,
            "content": content, "timestamp": time.time(),
            "notify": notify,
        })
        return index

    async def broadcast_transcript(
        self, role: str, text: str, entry_type: str = "speech",
        tool: str | None = None, tool_args: dict | None = None,
        tool_result: Any = None,
    ):
        self._transcript_id += 1
        entry = {"id": self._transcript_id, "role": role, "text": text, "type": entry_type}
        if tool:
            entry["tool"] = tool
        if tool_args is not None:
            entry["tool_args"] = tool_args
        if tool_result is not None:
            entry["tool_result"] = str(tool_result)[:500]
        await self._broadcast_msg({"type": "transcript_add", "entry": entry})

    async def broadcast_welcome(self):
        if not self._tools:
            return
        lines = ["# Minerva\n"]
        for tool in self._tools.values():
            base = type(tool).__bases__[0].__name__
            tag = {"InlineTool": "instant", "AsyncTool": "background", "SessionTool": "session"}.get(base, base)
            lines.append(f"### {tool.name}")
            lines.append(f"`{tag}` {tool.description}\n")
        lines += ["---", "*Say or type anything to get started.*"]
        await self.broadcast_board_post("minerva", "\n".join(lines))

    # ── Tool registration ────────────────────────────────────────────────────

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        tool.handle = _OrchestratorToolHandle(self, tool.name)
        self._register_handler(tool.name)
        logger.info(f"[Orchestrator] Registered: {tool.name}")

    def _register_handler(self, tool_name: str):
        async def _handler(params: FunctionCallParams):
            result = await self._execute_tool(tool_name, params)
            await params.result_callback(result.result if result else None)
        tool = self._tools.get(tool_name)
        cancel = tool.cancel_on_interruption if tool else True
        self.llm.register_function(tool_name, _handler, cancel_on_interruption=cancel)

    def get_tools_schema(self) -> ToolsSchema | None:
        schemas = [t.to_function_schema() for t in self._tools.values()]
        return ToolsSchema(standard_tools=schemas) if schemas else None

    # ── Session context ──────────────────────────────────────────────────────

    def enter_context(self, task_id: str) -> bool:
        state = self._find_task(task_id)
        if not state or not isinstance(state.tool, SessionTool):
            return False
        if task_id in self._active_contexts:
            return True
        self._active_contexts[task_id] = state
        self._rebuild_tools()
        self._on_task_change()
        logger.info(f"[Orchestrator] Entered context: {task_id} ({state.tool.name})")
        return True

    def exit_context(self, task_id: str) -> bool:
        if not self._active_contexts.pop(task_id, None):
            return False
        self._rebuild_tools()
        self._on_task_change()
        logger.info(f"[Orchestrator] Exited context: {task_id}")
        return True

    def toggle_context(self, task_id: str) -> bool:
        if task_id in self._active_contexts:
            self.exit_context(task_id)
            return False
        return self.enter_context(task_id)

    def _rebuild_tools(self):
        """Rebuild LLMContext.tools = base tools + active context tools."""
        schemas = [t.to_function_schema() for t in self._tools.values()]
        self._context_tool_map.clear()
        for task_id, state in self._active_contexts.items():
            for schema in state.tool.get_context_tools():
                schemas.append(schema)
                self._context_tool_map[schema.name] = task_id
                if not self.llm.has_function(schema.name):
                    self._register_context_handler(schema.name)
        self.context.set_tools(ToolsSchema(standard_tools=schemas))
        logger.debug(f"[Orchestrator] Tools: {len(schemas)} total, {len(self._context_tool_map)} context")

    def _register_context_handler(self, tool_name: str):
        async def _handler(params: FunctionCallParams):
            result = await self._execute_tool(tool_name, params)
            await params.result_callback(result.result if result else None)
        self.llm.register_function(tool_name, _handler, cancel_on_interruption=True)

    # ── Tool execution ───────────────────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, params: FunctionCallParams) -> TaskResult:
        kwargs = dict(params.arguments)
        await self.broadcast_transcript(
            "assistant", tool_name, entry_type="tool_call",
            tool=tool_name, tool_args=kwargs,
        )

        try:
            result = await self._dispatch(tool_name, kwargs)
        except Exception as e:
            logger.error(f"[Orchestrator] {tool_name} failed: {e}")
            result = TaskResult(result=f"Error: {e}")

        if result and result.board_content:
            await self.broadcast_board_post(self._author_for(tool_name), result.board_content, notify=result.notify)

        await self.broadcast_transcript(
            "assistant", tool_name, entry_type="tool_result",
            tool=tool_name, tool_result=result.result if result else None,
        )
        return result

    async def _dispatch(self, tool_name: str, kwargs: dict) -> TaskResult:
        """Route a tool call to the right handler. No error handling — caller wraps."""

        # Context tool (select_option, dismiss, etc.)
        if tool_name in self._context_tool_map:
            task_id = self._context_tool_map[tool_name]
            state = self._active_contexts.get(task_id)
            if state:
                return await state.tool.handle_context_call(tool_name, **kwargs)

        tool = self._tools.get(tool_name)
        if not tool:
            return TaskResult(result=f"Error: unknown tool {tool_name}")

        # SessionTool — existing session gets on_input, new one spawns
        if isinstance(tool, SessionTool):
            active = self._find_active_session(tool_name)
            if active:
                return await active.tool.on_input(**kwargs)
            task_id = await self.task_manager.spawn(tool, kwargs)
            if tool.auto_enter_context:
                self.enter_context(task_id)
            return TaskResult(
                result=f"Session {task_id} started",
                guide=f"{tool.name} session is running",
            )

        # AsyncTool — spawn
        if isinstance(tool, AsyncTool):
            task_id = await self.task_manager.spawn(tool, kwargs)
            return TaskResult(result=f"Task {task_id} started", guide=f"{tool.name} is running")

        # InlineTool — run directly
        return await tool.run(**kwargs)

    def _author_for(self, tool_name: str) -> str:
        """Board post author: owning session name for context tools, tool name otherwise."""
        task_id = self._context_tool_map.get(tool_name)
        if task_id:
            state = self._active_contexts.get(task_id)
            if state:
                return state.tool.name
        return tool_name

    # ── Popup actions ────────────────────────────────────────────────────────

    async def handle_popup_action(self, tool_name: str, action: str, data: dict):
        """Route a popup click to the owning session, then nudge the LLM."""
        state = self._find_context_by_tool(tool_name)
        if not state:
            logger.warning(f"[Orchestrator] No active session for popup: {tool_name}")
            return

        try:
            result = await state.tool.handle_context_call(action, **data)
        except Exception as e:
            logger.error(f"[Orchestrator] Popup {action} on {tool_name} failed: {e}")
            return

        if result and result.board_content:
            await self.broadcast_board_post(tool_name, result.board_content)
        await self.broadcast_transcript(
            "user", action, entry_type="popup_action",
            tool=tool_name, tool_args=data,
            tool_result=result.result if result else None,
        )

        # Inject as user text so the LLM processes the selection
        if result and result.guide and self.pipeline_task:
            frame = TranscriptionFrame(
                text=f"[{result.guide}]",
                user_id="popup",
                timestamp=str(time.time()),
            )
            await self.pipeline_task.queue_frame(frame)

    # ── Pre-turn preparation ─────────────────────────────────────────────────

    def prepare_for_turn(self):
        """Refresh tools and system message before each LLM turn.

        Called by BoardContextInjector on every LLMRunFrame. Rebuilds tools
        defensively (Pipecat may reset context.tools between turns) and
        injects task state, system state, and available context tools into
        the system message.
        """
        logger.debug("[Orchestrator] prepare_for_turn called")
        self._rebuild_tools()

        # Distribute system state to all tools
        sys_state = self.system_monitor.state if self.system_monitor else None
        for tool in self._tools.values():
            tool.system = sys_state

        # Gather active context info
        active_contexts = {}
        for task_id, state in self._active_contexts.items():
            tool_names = [t.name for t in state.tool.get_context_tools()]
            active_contexts[task_id] = (state.tool.name, tool_names)

        content = build_system_message(
            task_snapshot=self.task_manager.snapshot(),
            active_contexts=active_contexts,
            system_state=sys_state,
        )

        if self.context.messages:
            self.context.messages[0]["content"] = content
            logger.debug(f"[Orchestrator] System message: {len(content)} chars")

    # ── Input interception ────────────────────────────────────────────────────

    async def try_intercept(self, text: str) -> TaskResult | None:
        """Try to intercept user input via active session contexts.

        Returns a TaskResult if a session claimed the input, None otherwise.
        """
        for task_id, state in list(self._active_contexts.items()):
            if isinstance(state.tool, SessionTool):
                result = await state.tool.intercept(text)
                if result is not None:
                    logger.info(f"[Orchestrator] Input intercepted by {state.tool.name}: {text!r}")
                    await self.broadcast_transcript(
                        "user", text, entry_type="speech",
                    )
                    if result.board_content:
                        await self.broadcast_board_post(state.tool.name, result.board_content)
                    await self.broadcast_transcript(
                        "assistant", state.tool.name, entry_type="tool_result",
                        tool=state.tool.name, tool_result=result.result,
                    )
                    if state.tool.is_done:
                        self.exit_context(task_id)
                    return result
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_task(self, task_id: str) -> TaskState | None:
        return self.task_manager.active.get(task_id) or next(
            (s for s in self.task_manager.history if s.id == task_id), None
        )

    def _find_active_session(self, tool_name: str) -> TaskState | None:
        for state in self.task_manager.active.values():
            if isinstance(state.tool, SessionTool) and state.tool.name == tool_name:
                return state
        return None

    def _find_context_by_tool(self, tool_name: str) -> TaskState | None:
        for state in self._active_contexts.values():
            if isinstance(state.tool, SessionTool) and state.tool.name == tool_name:
                return state
        return None

    # ── TaskManager callbacks ────────────────────────────────────────────────

    def _on_notification(self, notif: Notification):
        logger.info(f"[Orchestrator] Notification: {notif.message}")
        asyncio.create_task(self.pipeline_task.queue_frame(TTSSpeakFrame(text=notif.message)))

    def _on_task_finalize(self, task_id: str):
        if task_id in self._active_contexts:
            self.exit_context(task_id)

    def _on_board_post(self, task_id: str, author: str, content: str, notify: bool = False):
        if not self._broadcast:
            return
        async def _post():
            index = await self.broadcast_board_post(author, content, notify=notify)
            state = self._find_task(task_id)
            if state:
                state.board_post_index = index
                self.task_manager._notify_change()
        asyncio.create_task(_post())

    def _on_task_change(self):
        if not self._broadcast:
            return
        tasks = self.task_manager.to_ui_list()
        active_ids = set(self._active_contexts)
        for t in tasks:
            state = self._find_task(t["id"])
            t["is_session"] = isinstance(state.tool, SessionTool) if state else False
            t["context_active"] = t["id"] in active_ids
        asyncio.create_task(self._broadcast({"type": "task_update", "tasks": tasks}))
