"""Core tools — session management, mute, board control, debugging.

These tools wire into orchestrator/system internals and are always registered.
"""

from __future__ import annotations
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from glarvis.tool import Intercept, InlineTool, Keyword, TaskResult

if TYPE_CHECKING:
    from glarvis.mute_gate import MuteGate
    from glarvis.orchestrator import Orchestrator


class Mute(InlineTool):
    name = "mute"
    description = "Mute voice input so Minerva stops listening. The user can say 'unmute' to resume."

    def __init__(self, mute_gate: MuteGate):
        self._gate = mute_gate

    def get_intercepts(self) -> list[Intercept]:
        return [Keyword("mute", self.run), Keyword("mute me", self.run)]

    async def run(self, **kwargs) -> TaskResult:
        await self._gate.set_muted(True)
        return TaskResult(result="muted", guide="Muted. Say unmute when you're ready.")


class OpenSettings(InlineTool):
    name = "open_settings"
    description = "Open or close the settings window."

    def get_intercepts(self) -> list[Intercept]:
        return [
            Keyword("settings", self.run),
            Keyword("open settings", self.run),
            Keyword("close settings", self._close),
        ]

    async def run(self, **kwargs) -> TaskResult:
        await self.handle.broadcast({"type": "open_settings"})
        return TaskResult(result="Settings opened.", guide="Opened.")

    async def _close(self, **kwargs) -> TaskResult:
        await self.handle.broadcast({"type": "close_settings"})
        return TaskResult(result="Settings closed.", guide="Closed.")


class CloseBoard(InlineTool):
    name = "close_board"
    description = "Close all board notification popups on screen."

    async def run(self, **kwargs) -> TaskResult:
        await self.handle.close_named_popup("board_notify")
        return TaskResult(result="closed", guide="Done")


class EnterSession(InlineTool):
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
            guide="It's on the board.",
            board_content=md,
            notify=True,
        )


class Shutdown(InlineTool):
    name = "shutdown"
    description = "Shut down Minerva completely."

    async def run(self, **kwargs) -> TaskResult:

        project_root = Path(__file__).resolve().parents[3]
        pids_to_kill = _find_project_pids(project_root)

        for pid in pids_to_kill:
            try:
                os.kill(pid, 9)
            except OSError:
                pass

        await asyncio.sleep(0.2)
        os._exit(0)


class Restart(InlineTool):
    name = "restart"
    description = "Restart Minerva. Kills all processes and relaunches."

    async def run(self, **kwargs) -> TaskResult:
        import asyncio

        project_root = Path(__file__).resolve().parents[3]
        start_script = project_root / "start.sh"
        if not start_script.exists():
            return TaskResult(result="start.sh not found", guide="Can't restart — start.sh is missing")

        # Collect PIDs to kill (Tauri app + node/vite from this project)
        pids_to_kill = _find_project_pids(project_root)

        # Write a restart script that waits for us to die, then relaunches
        if sys.platform == "win32":
            restart_bat = project_root / ".restart.bat"
            restart_bat.write_text(
                '@echo off\n'
                'timeout /t 3 /nobreak >nul\n'
                f'cd /d "{project_root}"\n'
                f'start "" bash "{start_script}"\n'
                'del "%~f0"\n',
                encoding="utf-8",
            )
            subprocess.Popen(
                ["cmd", "/c", str(restart_bat)],
                cwd=str(project_root),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            subprocess.Popen(
                ["bash", "-c", f'sleep 3 && bash "{start_script}"'],
                cwd=str(project_root),
                start_new_session=True,
                close_fds=True,
            )

        # Kill sibling processes (Tauri, node/vite)
        for pid in pids_to_kill:
            try:
                os.kill(pid, 9)
            except OSError:
                pass

        await asyncio.sleep(0.5)
        os._exit(0)


def _find_project_pids(project_root: Path) -> list[int]:
    """Find PIDs of Tauri app and node processes belonging to this project."""
    pids = []
    project_str = str(project_root).lower()
    my_pid = os.getpid()

    if sys.platform != "win32":
        return pids

    try:
        result = subprocess.run(
            ["wmic", "process", "where",
             "name='app.exe' or name='node.exe'",
             "get", "ProcessId,CommandLine,ExecutablePath", "/format:csv"],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split(",")
            if len(parts) < 4:
                continue
            # CSV: Node, CommandLine, ExecutablePath, ProcessId
            combined = ",".join(parts[1:-1]).lower()
            try:
                pid = int(parts[-1].strip())
            except ValueError:
                continue
            if pid == my_pid:
                continue
            if project_str in combined:
                pids.append(pid)
    except Exception:
        pass

    return pids


class DebugContext(InlineTool):
    name = "debug_context"
    description = "Show the full agent context (system prompt, messages, tools) on the board. For debugging."
    display = "board"

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator

    async def run(self, **kwargs) -> TaskResult:
        context = self._orchestrator.context
        messages = context.messages or []

        lines = ["# Agent Context Debug\n"]

        if messages and messages[0].get("role") == "system":
            sys_content = messages[0].get("content", "")
            has_task_state = "[Task State]" in sys_content
            has_system_state = "[System State]" in sys_content
            lines.append("## System Message\n")
            lines.append(f"```\n{sys_content[:3000]}\n```\n")
            lines.append(f"*Task context injected: {'Yes' if has_task_state else 'No (no active/recent tasks)'}*")
            lines.append(f"*System state injected: {'Yes' if has_system_state else 'No (monitor may not be running)'}*\n")
            start = 1
        else:
            start = 0

        for i in range(start, len(messages)):
            msg = messages[i]
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = str(content)
            preview = content[:1500] if len(content) > 1500 else content
            lines.append(f"## Message {i}: `{role}`\n")
            lines.append(f"```\n{preview}\n```\n")

        tools = self._orchestrator._tools
        if tools:
            lines.append(f"## Registered Tools ({len(tools)})\n")
            for name in tools:
                lines.append(f"- `{name}`")

        # System state (explicit section for easy inspection)
        sys_monitor = self._orchestrator.system_monitor
        lines.append("\n## System State\n")
        if sys_monitor:
            state = sys_monitor.state
            summary = state.summary()
            lines.append(f"*Monitor running: Yes (interval={sys_monitor.interval}s)*")
            lines.append(f"*Windows: {len(state.windows)}, Foreground ID: {state.foreground_id}*\n")
            lines.append(f"```\n{summary}\n```")
        else:
            lines.append("*No system monitor attached to orchestrator.*")

        # Intercept registry
        orch = self._orchestrator
        lines.append("\n## Intercepts\n")
        gk = list(orch._global_keywords.keys())
        ck = list(orch._context_keywords.keys())
        lines.append(f"*Global keywords: {gk if gk else 'none'}*")
        lines.append(f"*Global functions: {len(orch._global_functions)}*")
        lines.append(f"*Context keywords: {ck if ck else 'none'}*")
        lines.append(f"*Context functions: {len(orch._context_functions)}*")

        snapshot = self._orchestrator.task_manager.snapshot()
        lines.append("\n## Task Manager Snapshot\n")
        if snapshot:
            lines.append(f"```\n{snapshot}\n```")
        else:
            lines.append("*Empty — no active tasks, no recent history, no pending notifications.*")

        return TaskResult(
            result="Debug context posted to board",
            board_content="\n".join(lines),
            notify=True,
        )
