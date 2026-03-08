"""TaskManager — central state and lifecycle manager for async tasks.

Tasks post updates here. The orchestrator subscribes and injects a snapshot
into the LLM context before each turn. Notifications are queued and delivered
either through the agent (speak) or directly (terminal/UI)."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from loguru import logger

from glarvis.tool import AsyncTool, NotificationLevel, TaskResult


@dataclass
class TaskState:
    """Tracks a single running or completed task."""

    id: str
    tool: AsyncTool
    status: Literal["pending", "running", "completed", "failed", "expired"] = "pending"
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    result: TaskResult | None = None
    progress: str | None = None  # latest progress message from the tool
    board_post_index: int | None = None  # index into frontend boardStream
    _task: asyncio.Task | None = field(default=None, repr=False)


@dataclass
class Notification:
    """A pending notification for the user."""

    task_id: str
    message: str
    level: NotificationLevel


class TaskManager:
    """Central state manager for all tasks.

    Usage::

        task_manager = TaskManager()

        # Orchestrator subscribes to get notified of changes
        task_manager.on_notification = my_notification_handler

        # Spawn a task
        task_id = await task_manager.spawn(my_tool, kwargs={"query": "auth"})

        # Get current state for LLM context injection
        snapshot = task_manager.snapshot()
    """

    def __init__(self, max_history: int = 20):
        self.active: dict[str, TaskState] = {}
        self.history: deque[TaskState] = deque(maxlen=max_history)
        self.pending_notifications: list[Notification] = []
        self._counter = 0

        # Callbacks (set by orchestrator)
        self.on_notification: Callable[[Notification], Any] | None = None
        self.on_change: Callable[[], Any] | None = None
        self.on_board_post: Callable[[str, str, str, bool], Any] | None = None  # (task_id, author, content, notify)
        self.on_finalize: Callable[[str], Any] | None = None  # (task_id)

    def _next_id(self) -> str:
        self._counter += 1
        return f"task_{self._counter}"

    async def spawn(self, tool: AsyncTool, kwargs: dict[str, Any]) -> str:
        """Spawn a tool as an async task, tracked by the task manager."""
        task_id = self._next_id()
        state = TaskState(id=task_id, tool=tool, status="running")
        self.active[task_id] = state

        async def _run():
            try:
                await tool.on_start()
                logger.info(f"[TaskManager] {task_id} ({tool.name}) started")

                if tool.ttl:
                    result = await asyncio.wait_for(tool.run(**kwargs), timeout=tool.ttl)
                else:
                    result = await tool.run(**kwargs)

                state.status = "completed"
                state.result = result
                state.completed_at = time.time()
                await tool.on_complete(result)
                self._handle_completion(task_id, state)

            except asyncio.TimeoutError:
                state.status = "expired"
                state.completed_at = time.time()
                await tool.on_expire()
                logger.warning(f"[TaskManager] {task_id} ({tool.name}) expired (TTL={tool.ttl}s)")
                self._finalize(task_id)

            except Exception as e:
                state.status = "failed"
                state.completed_at = time.time()
                state.result = TaskResult(result=None, guide=f"Error: {e}")
                logger.error(f"[TaskManager] {task_id} ({tool.name}) failed: {e}")
                self._finalize(task_id)

        state._task = asyncio.create_task(_run())
        self._notify_change()
        return task_id

    def _notify_change(self):
        """Notify listeners that task state changed."""
        if self.on_change:
            self.on_change()

    def post_progress(self, task_id: str, update: str):
        """Called by tools to report progress."""
        if task_id in self.active:
            self.active[task_id].progress = update
            logger.debug(f"[TaskManager] {task_id} progress: {update}")
            self._notify_change()

    def _handle_completion(self, task_id: str, state: TaskState):
        """Route completion based on tool metadata."""
        tool = state.tool
        result = state.result

        # Display routing
        if tool.display in ("board", "both") and result and result.board_content:
            logger.info(f"[TaskManager] {tool.name} posted to board")
            if self.on_board_post:
                self.on_board_post(task_id, tool.name, result.board_content, result.notify)

        # Notification routing
        if tool.notification == "silent":
            pass
        elif tool.notification in ("notify", "interrupt"):
            msg = (
                result.guide
                if result and result.guide
                else f"{tool.name} has completed"
            )
            notif = Notification(task_id=task_id, message=msg, level=tool.notification)
            self.pending_notifications.append(notif)
            if self.on_notification:
                self.on_notification(notif)

        self._finalize(task_id)

    def _finalize(self, task_id: str):
        """Move task from active to history."""
        if task_id in self.active:
            state = self.active.pop(task_id)
            self.history.append(state)
            if self.on_finalize:
                self.on_finalize(task_id)
            self._notify_change()

    def drain_notifications(self) -> list[Notification]:
        """Pop all pending notifications. Called by orchestrator before LLM turn."""
        notifs = self.pending_notifications[:]
        self.pending_notifications.clear()
        return notifs

    def snapshot(self) -> str | None:
        """Render current task state as text for LLM context injection.

        Returns None if there's nothing to report, so we don't waste tokens."""
        lines = []

        for state in self.active.values():
            elapsed = time.time() - state.started_at
            status = state.tool.task_display_status(elapsed)
            if state.progress:
                status += f' -- "{state.progress}"'
            lines.append(f"  [ACTIVE] {status}")

        for state in list(self.history)[-5:]:
            if state.status == "completed" and state.result and state.result.guide:
                lines.append(f"  [DONE] {state.tool.name} -- {state.result.guide}")
            elif state.status == "failed" and state.result and state.result.guide:
                lines.append(f"  [FAILED] {state.tool.name} -- {state.result.guide}")

        for notif in self.pending_notifications:
            lines.append(f"  [NOTIFIED] {notif.message}")

        if not lines:
            return None

        return "[Task State]\n" + "\n".join(lines)

    def to_ui_list(self) -> list[dict]:
        """Serialize task state for the frontend UI."""
        now = time.time()
        items = []

        # Always show active tasks
        for state in self.active.values():
            items.append({
                "id": state.id,
                "name": state.tool.name,
                "status": state.status,
                "elapsed": now - state.started_at,
                "progress": state.progress,
                "board_post_index": state.board_post_index,
            })

        # Only show completed tasks if persist_in_display is True
        for state in list(self.history)[-5:]:
            if not state.tool.persist_in_display:
                continue
            elapsed = (state.completed_at or now) - state.started_at
            items.append({
                "id": state.id,
                "name": state.tool.name,
                "status": state.status,
                "elapsed": elapsed,
                "progress": state.result.guide if state.result else None,
                "board_post_index": state.board_post_index,
            })

        return items
