"""Example tools to demonstrate the tool type system."""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from glarvis.tool import AsyncTool, InlineTool, TaskResult

if TYPE_CHECKING:
    from glarvis.orchestrator import Orchestrator


class GetTime(InlineTool):
    """Returns the current time. Runs inline, agent speaks the answer."""

    name = "get_time"
    description = "Get the current date and time."

    async def run(self, **kwargs) -> TaskResult:
        from datetime import datetime

        now = datetime.now().strftime("%I:%M %p on %A, %B %d")
        return TaskResult(result=now, guide=f"It's {now}")


class SearchFiles(AsyncTool):
    """Searches files by pattern. Runs async, posts results to the board."""

    name = "search_files"
    description = (
        "Search for files in the current project by name pattern. "
        "Results will be displayed on the board."
    )
    parameters = {
        "pattern": {"type": "string", "description": "Filename pattern to search for (e.g. '*.py', 'auth')"}
    }
    required = ["pattern"]
    ttl = 15

    async def run(self, pattern: str = "", **kwargs) -> TaskResult:
        import glob

        matches = glob.glob(f"**/*{pattern}*", recursive=True)
        await asyncio.sleep(1)
        return TaskResult(
            result=matches,
            guide=f"Found {len(matches)} files matching {pattern}",
            board_content="\n".join(matches[:20]) if matches else "No files found",
        )

    def task_display_status(self, elapsed: float) -> str:
        return f"search_files (searching, {elapsed:.1f}s)"


class ListDirectory(InlineTool):
    """Lists files in a directory. Runs inline, posts to board."""

    name = "list_directory"
    description = (
        "List files in a directory. Results display on the board, "
        "don't read them out loud."
    )
    parameters = {
        "path": {"type": "string", "description": "Directory path to list (default: current directory)"}
    }
    display = "board"

    async def run(self, path: str = ".", **kwargs) -> TaskResult:
        try:
            entries = os.listdir(path)
            listing = "\n".join(sorted(entries))
            return TaskResult(
                result=entries,
                guide=f"Listed {len(entries)} items in {path}",
                board_content=listing,
            )
        except OSError as e:
            return TaskResult(result=None, guide=f"Error listing directory: {e}")


class WriteBoard(InlineTool):
    """Write arbitrary content to the board."""

    name = "write_board"
    description = "Write markdown or text content to the board display. Use this to show explanations, notes, summaries, code, or any visual content to the user."
    parameters = {
        "content": {"type": "string", "description": "Markdown content to display on the board"},
        "title": {"type": "string", "description": "Optional title for the board post"},
    }
    required = ["content"]
    display = "board"

    async def run(self, content: str = "", title: str = "", **kwargs) -> TaskResult:
        if title:
            md = f"# {title}\n\n{content}"
        else:
            md = content
        return TaskResult(
            result="Posted to board",
            board_content=md,
        )


class DebugContext(InlineTool):
    """Debug tool that dumps the full LLM context to the board."""

    name = "debug_context"
    description = "Show the full agent context (system prompt, messages, tools) on the board. For debugging."
    display = "board"

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

    async def run(self, **kwargs) -> TaskResult:
        context = self._orchestrator.context
        messages = context.messages or []

        lines = ["# Agent Context Debug\n"]

        # Show system message (with any injected task state)
        if messages and messages[0].get("role") == "system":
            sys_content = messages[0].get("content", "")
            has_task_state = "[Task State]" in sys_content
            lines.append("## System Message\n")
            lines.append(f"```\n{sys_content[:3000]}\n```\n")
            lines.append(f"*Task context injected: {'Yes' if has_task_state else 'No (no active/recent tasks)'}*\n")
            start = 1
        else:
            start = 0

        # Show conversation messages
        for i in range(start, len(messages)):
            msg = messages[i]
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = str(content)
            preview = content[:1500] if len(content) > 1500 else content
            lines.append(f"## Message {i}: `{role}`\n")
            lines.append(f"```\n{preview}\n```\n")

        # Show registered tools
        tools = self._orchestrator._tools
        if tools:
            lines.append(f"## Registered Tools ({len(tools)})\n")
            for name in tools:
                lines.append(f"- `{name}`")

        # Show task manager state
        snapshot = self._orchestrator.task_manager.snapshot()
        lines.append(f"\n## Task Manager Snapshot\n")
        if snapshot:
            lines.append(f"```\n{snapshot}\n```")
        else:
            lines.append("*Empty — no active tasks, no recent history, no pending notifications.*")

        return TaskResult(
            result="Debug context posted to board",
            board_content="\n".join(lines),
        )


class EnterSession(InlineTool):
    """Activate a session's context, making its tools available."""

    name = "enter_session"
    description = "Enter an active session's context by task number, making its tools available. Use the number from the task ID (e.g. 1 for task_1)."
    parameters = {
        "id": {"type": "integer", "description": "Task number to enter context for"},
    }
    required = ["id"]

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

    async def run(self, id: int = 0, **kwargs) -> TaskResult:
        task_id = f"task_{id}"
        if self._orchestrator.enter_context(task_id):
            return TaskResult(result=f"Entered context for {task_id}", guide="Context activated")
        return TaskResult(result=f"Failed to enter context for {task_id}", guide="No such session")


class ExitSession(InlineTool):
    """Deactivate a session's context, removing its temporary tools."""

    name = "exit_session"
    description = "Exit an active session's context by task number, removing its temporary tools."
    parameters = {
        "id": {"type": "integer", "description": "Task number to exit context for"},
    }
    required = ["id"]

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

    async def run(self, id: int = 0, **kwargs) -> TaskResult:
        task_id = f"task_{id}"
        if self._orchestrator.exit_context(task_id):
            return TaskResult(result=f"Exited context for {task_id}", guide="Context deactivated")
        return TaskResult(result=f"No active context for {task_id}", guide="Nothing to exit")


class ListTools(InlineTool):
    """Lists all available tools on the board."""

    name = "list_tools"
    description = "Show all available tools and what they do. Posts the list to the board."
    display = "board"

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

    async def run(self, **kwargs) -> TaskResult:
        tools = self._orchestrator._tools
        if not tools:
            return TaskResult(result="No tools registered", guide="No tools available")

        lines = ["# Available Tools\n"]
        for tool in tools.values():
            tool_type = type(tool).__bases__[0].__name__
            tag = {"InlineTool": "instant", "AsyncTool": "background", "SessionTool": "session"}.get(tool_type, tool_type)
            lines.append(f"### {tool.name}")
            lines.append(f"`{tag}` {tool.description}\n")

        md = "\n".join(lines)
        names = ", ".join(tools.keys())
        return TaskResult(
            result=names,
            guide=f"It's on the board.",
            board_content=md,
        )
